"""Consulta de eventos (usada pela API e pela busca em linguagem natural) e serialização para o front."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from ..models import Evento, Lugar
from . import taxonomia
from .modelos import (EventoArtista, EventoArtistaLink, EventoCategoria, EventoCategoriaLink, EventoFonteLink, EventoImagem, EventoLocal, EventoOrganizador)
from .normalizar import norm_texto

ATIVOS = ("agendado", "adiado", "remarcado", "desconhecido")


@dataclass
class Filtros:
    q: str | None = None
    categoria: str | None = None           # slug (inclui subcategorias)
    cidade: str | None = None
    estado: str | None = None
    pais: str | None = None
    data_de: datetime | None = None        # UTC
    data_ate: datetime | None = None       # UTC (exclusivo)
    preco_max: float | None = None
    gratuito: bool | None = None
    tipo_local: str | None = None          # restaurante | bar (estabelecimento do Turiz vinculado ao evento)
    local: str | None = None               # trecho do nome do local
    lugar_id: int | None = None
    fonte: str | None = None
    com_imagem: bool | None = None
    incluir_cancelados: bool = False
    incluir_encerrados: bool = False
    incluir_sem_data: bool = False
    artista: str | None = None
    ordem: str = "data"                    # data | preco | recentes
    extras: list = field(default_factory=list)


def _ids_categoria(db: Session, slug: str) -> list[int]:
    slugs = {slug} | taxonomia.filhas_de(slug)
    return list(db.scalars(select(EventoCategoria.id).where(EventoCategoria.slug.in_(slugs))))


def montar(db: Session, f: Filtros, agora: datetime | None = None):
    agora = agora or datetime.now(timezone.utc)
    st = select(Evento)
    est = list(ATIVOS) + (["cancelado"] if f.incluir_cancelados else []) + (["encerrado"] if f.incluir_encerrados else [])
    st = st.where(Evento.status.in_(est))
    if not f.incluir_encerrados:                       # nunca mostra vencido como futuro
        st = st.where(or_(Evento.inicio >= agora - timedelta(hours=3), Evento.fim >= agora, and_(Evento.inicio.is_(None), f.incluir_sem_data)))
    elif not f.incluir_sem_data:
        st = st.where(Evento.inicio.is_not(None))
    if f.data_de:
        st = st.where(Evento.inicio >= f.data_de)
    if f.data_ate:
        st = st.where(Evento.inicio < f.data_ate)
    if f.q:                                            # cada palavra precisa aparecer no título, local ou artista
        for tok in norm_texto(f.q).split():
            st = st.where(or_(Evento.nome_norm.like(f"%{tok}%"), Evento.local_nome.ilike(f"%{tok}%"),
                              Evento.local_id.in_(select(EventoLocal.id).where(EventoLocal.nome_norm.like(f"%{tok}%"))),
                              Evento.id.in_(select(EventoArtistaLink.evento_id).join(EventoArtista, EventoArtista.id == EventoArtistaLink.artista_id).where(EventoArtista.nome_norm.like(f"%{tok}%")))))
    if f.artista:
        st = st.where(Evento.id.in_(select(EventoArtistaLink.evento_id).join(EventoArtista, EventoArtista.id == EventoArtistaLink.artista_id)
                                    .where(EventoArtista.nome_norm.like(f"%{norm_texto(f.artista)}%"))))
    if f.categoria:
        ids = _ids_categoria(db, f.categoria)
        st = st.where(Evento.id.in_(select(EventoCategoriaLink.evento_id).where(EventoCategoriaLink.categoria_id.in_(ids or [-1]))))
    if f.cidade or f.estado or f.pais:
        sub = select(EventoLocal.id)
        if f.cidade:
            sub = sub.where(func.lower(EventoLocal.cidade) == f.cidade.lower())
        if f.estado:
            sub = sub.where(func.lower(EventoLocal.estado) == f.estado.lower())
        if f.pais:
            sub = sub.where(func.lower(EventoLocal.pais) == f.pais.lower())
        st = st.where(Evento.local_id.in_(sub))
    if f.local:
        st = st.where(Evento.local_nome.ilike(f"%{f.local}%"))
    if f.lugar_id is not None:
        l = db.get(Lugar, f.lugar_id)
        st = st.where(Evento.lugar_fonte == (l.fonte if l else "#"), Evento.lugar_fonte_id == (l.fonte_id if l else "#"))
    if f.tipo_local:
        st = st.where(Evento.id.in_(select(Evento.id).join(Lugar, and_(Lugar.fonte == Evento.lugar_fonte, Lugar.fonte_id == Evento.lugar_fonte_id)).where(Lugar.tipo == f.tipo_local)))
    if f.gratuito:
        st = st.where(or_(Evento.gratuito.is_(True), Evento.preco_max == 0))
    if f.preco_max is not None:
        st = st.where(or_(Evento.gratuito.is_(True), Evento.preco_min <= f.preco_max))   # preço desconhecido não entra: não presumimos
    if f.fonte:
        st = st.where(Evento.id.in_(select(EventoFonteLink.evento_id).where(EventoFonteLink.fonte == f.fonte)))
    if f.com_imagem:
        st = st.where(Evento.imagem_url != "")
    return st


def ordenar(st, ordem: str):
    if ordem == "preco":
        return st.order_by(Evento.preco_min.is_(None), Evento.preco_min, Evento.inicio)
    if ordem == "recentes":
        return st.order_by(Evento.coletado_em.desc())
    return st.order_by(Evento.inicio.is_(None), Evento.inicio, Evento.id)


def _utc(d):
    """Datas guardadas em UTC; bancos sem fuso (SQLite) as devolvem 'ingênuas'. O cliente precisa do fuso para exibir no horário certo."""
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def serializar(db: Session, eventos: list[Evento], completo: bool = False) -> list[dict]:
    if not eventos:
        return []
    ids = [e.id for e in eventos]
    locais = {l.id: l for l in db.scalars(select(EventoLocal).where(EventoLocal.id.in_([e.local_id for e in eventos if e.local_id])))} if any(e.local_id for e in eventos) else {}
    cats: dict[int, list] = {}
    for link, c in db.execute(select(EventoCategoriaLink, EventoCategoria).join(EventoCategoria, EventoCategoria.id == EventoCategoriaLink.categoria_id).where(EventoCategoriaLink.evento_id.in_(ids))):
        cats.setdefault(link.evento_id, []).append({"slug": c.slug, "nome": c.nome, "grupo": c.grupo, "primaria": link.primaria})
    fontes: dict[int, list] = {}
    for l in db.scalars(select(EventoFonteLink).where(EventoFonteLink.evento_id.in_(ids)).order_by(EventoFonteLink.id)):
        fontes.setdefault(l.evento_id, []).append({"fonte": l.fonte, "plataforma": l.plataforma, "url": l.url, "ingresso_url": l.ingresso_url})
    arts: dict[int, list] = {}
    for link, a in db.execute(select(EventoArtistaLink, EventoArtista).join(EventoArtista, EventoArtista.id == EventoArtistaLink.artista_id).where(EventoArtistaLink.evento_id.in_(ids)).order_by(EventoArtistaLink.ordem)):
        arts.setdefault(link.evento_id, []).append({"nome": a.nome, "url": a.url})
    imgs: dict[int, list] = {}
    if completo:
        for i in db.scalars(select(EventoImagem).where(EventoImagem.evento_id.in_(ids), EventoImagem.fallback.is_(False))):
            imgs.setdefault(i.evento_id, []).append({"url": i.url, "largura": i.largura, "altura": i.altura, "tipo": i.tipo, "credito": i.credito})
    orgs = {o.id: o for o in db.scalars(select(EventoOrganizador).where(EventoOrganizador.id.in_([e.organizador_id for e in eventos if e.organizador_id])))} if any(e.organizador_id for e in eventos) else {}
    lugares = {}
    for e in eventos:
        if e.lugar_fonte_id and (e.lugar_fonte, e.lugar_fonte_id) not in lugares:
            l = db.scalar(select(Lugar).where(Lugar.fonte == e.lugar_fonte, Lugar.fonte_id == e.lugar_fonte_id))
            lugares[(e.lugar_fonte, e.lugar_fonte_id)] = {"id": l.id, "nome": l.nome, "tipo": l.tipo} if l else None
    saida = []
    for e in eventos:
        L = locais.get(e.local_id)
        d = {"id": e.id, "titulo": e.titulo, "descricao": e.descricao if completo else (e.descricao or "")[:300], "inicio": _utc(e.inicio), "fim": _utc(e.fim), "fuso": e.fuso,
             "status": e.status, "data_incerta": e.data_incerta,
             "local": {"nome": (L.nome if L else "") or e.local_nome, "endereco": (L.endereco if L else "") or e.endereco, "cidade": L.cidade if L else "", "estado": L.estado if L else "",
                       "pais": L.pais if L else "", "lat": (L.lat if L and L.lat is not None else e.lat), "lon": (L.lon if L and L.lon is not None else e.lon)},
             "categorias": cats.get(e.id, []), "imagem": {"url": e.imagem_url} if e.imagem_url else None,
             "preco_min": e.preco_min, "preco_max": e.preco_max, "moeda": e.moeda, "gratuito": e.gratuito,
             "ingresso_url": e.ingresso_url, "url": e.url_oficial or e.url, "fontes": fontes.get(e.id, []), "artistas": arts.get(e.id, []),
             "lugar": lugares.get((e.lugar_fonte, e.lugar_fonte_id)) if e.lugar_fonte_id else None}
        if completo:
            o = orgs.get(e.organizador_id)
            d.update(imagens=imgs.get(e.id, []), organizador={"nome": o.nome, "tipo": o.tipo, "url": o.url} if o else None, classificacao_indicativa=e.classificacao_indicativa,
                     acessibilidade=e.acessibilidade, atualizado_em=_utc(e.atualizado_em), visto_em=_utc(e.visto_em))
        saida.append(d)
    return saida


def listar(db: Session, f: Filtros, limit: int = 50, offset: int = 0, agora=None) -> dict:
    st = montar(db, f, agora)
    total = db.scalar(select(func.count()).select_from(st.subquery()))
    itens = db.scalars(ordenar(st, f.ordem).limit(limit).offset(offset)).all()
    return {"total": total, "itens": serializar(db, list(itens))}


def categorias_com_contagem(db: Session, agora=None) -> list[dict]:
    """Árvore de categorias com a contagem de eventos futuros (incluindo subcategorias)."""
    base = montar(db, Filtros(), agora).subquery()
    cont = dict(db.execute(select(EventoCategoria.slug, func.count(func.distinct(EventoCategoriaLink.evento_id))).join(EventoCategoriaLink, EventoCategoriaLink.categoria_id == EventoCategoria.id)
                           .where(EventoCategoriaLink.evento_id.in_(select(base.c.id))).group_by(EventoCategoria.slug)).all())
    return [{"slug": s, "nome": n, "grupo": g, "pai": p, "total": cont.get(s, 0)} for s, n, g, p in taxonomia.CATEGORIAS]
