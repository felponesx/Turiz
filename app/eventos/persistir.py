"""Grava eventos no banco: valida -> reconhece duplicidade -> cria/atualiza o evento canônico + tabelas relacionadas.

- o mesmo evento em várias fontes vira UMA linha em `eventos` com vários `evento_fonte_links`;
- pares duvidosos entram na fila `evento_duplicatas` (revisão humana), sem mesclar sozinhos;
- toda mudança relevante vai para `evento_atualizacoes`; cancelados e vencidos NUNCA são apagados (só mudam de status).
"""
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Evento, Lugar
from . import dedup, taxonomia
from .bruto import EventoBruto, ImagemBruta, validar
from .modelos import (EventoArtista, EventoArtistaLink, EventoAtualizacao, EventoCategoria, EventoCategoriaLink, EventoDuplicata,
                      EventoFonte, EventoFonteLink, EventoImagem, EventoLocal, EventoOrganizador)
from .normalizar import norm_nome_evento, norm_texto, status_de

CAMPOS_REGISTRADOS = ("titulo", "inicio", "fim", "status", "local_nome", "preco_min", "preco_max", "url", "ingresso_url", "descricao")
JANELA_DEDUP = timedelta(days=1)


@dataclass
class Resumo:
    coletados: int = 0
    novos: int = 0
    atualizados: int = 0
    inalterados: int = 0
    duplicados: int = 0      # anúncios que viraram link de um evento já existente (mesmo evento em outra fonte)
    revisao: int = 0         # pares enviados para revisão humana
    descartados: int = 0
    motivos_descarte: Counter = field(default_factory=Counter)


def _agora():
    return datetime.now(timezone.utc)


def _utc(d):
    if d is None:
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)


def _txt(v) -> str:
    return "" if v is None else str(v)[:500]


def semear_categorias(db: Session) -> dict[str, int]:
    """Cria as categorias que faltam (idempotente). Devolve {slug: id}."""
    existentes = {c.slug: c.id for c in db.scalars(select(EventoCategoria))}
    for ordem, (slug, nome, grupo, pai) in enumerate(taxonomia.CATEGORIAS):
        if slug not in existentes:
            c = EventoCategoria(slug=slug, nome=nome, grupo=grupo, pai_id=existentes.get(pai) if pai else None, ordem=ordem)
            db.add(c)
            db.flush()
            existentes[slug] = c.id
    return existentes


# ----------------------------------------------------------------------------- entidades relacionadas
def obter_local(db: Session, L, fonte: str) -> EventoLocal | None:
    if L is None or not (L.nome or L.endereco or (L.lat is not None)):
        return None
    nome_norm = norm_texto(L.nome)
    obj = None
    if L.fonte_id:
        obj = db.scalar(select(EventoLocal).where(EventoLocal.fonte == fonte, EventoLocal.fonte_id == L.fonte_id))
    if obj is None and nome_norm:
        cand = db.scalars(select(EventoLocal).where(EventoLocal.nome_norm == nome_norm, EventoLocal.cidade == (L.cidade or ""))).first()
        obj = cand
    if obj is None:
        # sem id na fonte: chave sintética estável (a restrição única fonte+fonte_id não aceita vários vazios)
        chave = L.fonte_id or f"n:{nome_norm}|{norm_texto(L.cidade)}" if (L.fonte_id or nome_norm) else f"g:{L.lat:.5f},{L.lon:.5f}" if L.lat is not None else f"e:{norm_texto(L.endereco)}"
        obj = EventoLocal(fonte=fonte if L.fonte_id else "_sem_id", fonte_id=chave)
        db.add(obj)
    for campo in ("nome", "endereco", "cidade", "estado", "pais", "cep"):
        v = getattr(L, campo)
        if v and not getattr(obj, campo, ""):
            setattr(obj, campo, v)
    if L.lat is not None and obj.lat is None:
        obj.lat, obj.lon = L.lat, L.lon
    obj.nome_norm = norm_texto(obj.nome)
    db.flush()
    return obj


def obter_organizador(db: Session, p, fonte: str) -> EventoOrganizador | None:
    if p is None or not p.nome:
        return None
    obj = None
    if p.fonte_id:
        obj = db.scalar(select(EventoOrganizador).where(EventoOrganizador.fonte == fonte, EventoOrganizador.fonte_id == p.fonte_id))
    if obj is None:
        obj = db.scalars(select(EventoOrganizador).where(EventoOrganizador.nome_norm == norm_texto(p.nome))).first()
    if obj is None:
        obj = EventoOrganizador(nome=p.nome, nome_norm=norm_texto(p.nome), tipo=p.tipo or "organizador", fonte=fonte if p.fonte_id else "",
                                fonte_id=p.fonte_id or "", url=p.url)
        db.add(obj)
        db.flush()
    return obj


def obter_artista(db: Session, a, fonte: str) -> EventoArtista:
    obj = None
    if a.fonte_id:
        obj = db.scalar(select(EventoArtista).where(EventoArtista.fonte == fonte, EventoArtista.fonte_id == a.fonte_id))
    if obj is None:
        obj = db.scalars(select(EventoArtista).where(EventoArtista.nome_norm == norm_texto(a.nome), EventoArtista.fonte_id == "")).first() if not a.fonte_id else None
    if obj is None:
        obj = EventoArtista(nome=a.nome, nome_norm=norm_texto(a.nome), fonte=fonte if a.fonte_id else "", fonte_id=a.fonte_id or "", url=a.url, imagem_url=a.imagem_url)
        db.add(obj)
        db.flush()
    return obj


def melhor_imagem(imagens: list[ImagemBruta]) -> str:
    """URL da foto principal: ignora imagens 'fallback' (genéricas da fonte); prefere largura próxima de 1024 px."""
    reais = [i for i in imagens if not i.fallback and i.tipo == "principal"]
    if not reais:
        return ""
    return min(reais, key=lambda i: abs((i.largura or 640) - 1024)).url


def _tipo_lugar(db: Session, local: EventoLocal | None) -> str:
    if local and local.lugar_fonte_id:
        l = db.scalar(select(Lugar).where(Lugar.fonte == local.lugar_fonte, Lugar.fonte_id == local.lugar_fonte_id))
        return l.tipo if l else ""
    return ""


def _gravar_relacionados(db: Session, ev: Evento, b: EventoBruto, fonte: str, local: EventoLocal | None) -> None:
    ja = {i.url for i in db.scalars(select(EventoImagem).where(EventoImagem.evento_id == ev.id))}
    for i in b.imagens:
        if i.url not in ja:
            db.add(EventoImagem(evento_id=ev.id, url=i.url, largura=i.largura, altura=i.altura, proporcao=i.proporcao, tipo=i.tipo,
                                fallback=i.fallback, fonte=fonte, credito=i.credito))
            ja.add(i.url)
    ligados = {l.artista_id for l in db.scalars(select(EventoArtistaLink).where(EventoArtistaLink.evento_id == ev.id))}
    for ordem, a in enumerate(b.artistas):
        art = obter_artista(db, a, fonte)
        if art.id not in ligados:
            db.add(EventoArtistaLink(evento_id=ev.id, artista_id=art.id, ordem=ordem))
            ligados.add(art.id)
    cats = semear_categorias(db)
    atuais = {l.categoria_id for l in db.scalars(select(EventoCategoriaLink).where(EventoCategoriaLink.evento_id == ev.id))}
    for slug, primaria, origem in taxonomia.classificar(ev.titulo, ev.descricao, b.categorias, _tipo_lugar(db, local)):
        cid = cats.get(slug)
        if cid and cid not in atuais:
            db.add(EventoCategoriaLink(evento_id=ev.id, categoria_id=cid, primaria=primaria and not atuais, origem=origem))
            atuais.add(cid)
            if primaria and not ev.categoria:
                ev.categoria = slug
    if not ev.categoria and atuais:
        ev.categoria = next((s for s, i in cats.items() if i in atuais), "")


def _registrar(db: Session, ev: Evento, fonte: str, tipo: str, campo: str, antigo, novo) -> None:
    db.add(EventoAtualizacao(evento_id=ev.id, fonte=fonte, tipo=tipo, campo=campo, valor_antigo=_txt(antigo), valor_novo=_txt(novo)))


def _valores(b: EventoBruto, local: EventoLocal | None) -> dict:
    """Campos do evento canônico a partir do que a fonte informou (só o que veio preenchido)."""
    v = {"titulo": b.titulo, "descricao": b.descricao, "inicio": b.inicio, "fim": b.fim, "fuso": b.fuso, "classificacao_indicativa": b.classificacao_indicativa,
         "acessibilidade": b.acessibilidade, "preco_min": b.preco_min, "preco_max": b.preco_max, "moeda": b.moeda, "url": b.url,
         "url_oficial": b.url, "ingresso_url": b.ingresso_url, "imagem_url": melhor_imagem(b.imagens)}
    if local:
        v.update({"local_nome": local.nome, "endereco": local.endereco or "", "lat": local.lat, "lon": local.lon})
        v["local_id"] = local.id
    return {k: x for k, x in v.items() if x not in (None, "")}


def _aplicar(db: Session, ev: Evento, b: EventoBruto, fonte: str, local, sobrescrever: bool) -> bool:
    """Aplica os campos da fonte. `sobrescrever`: a fonte manda (é a mesma fonte, ou tem prioridade maior)."""
    mudou = False
    for campo, novo in _valores(b, local).items():
        atual = getattr(ev, campo, None)
        if campo in ("inicio", "fim"):
            atual, novo_cmp = _utc(atual), _utc(novo)
        else:
            novo_cmp = novo
        if atual in (None, "", 0) or (sobrescrever and atual != novo_cmp):
            if atual not in (None, "") and campo in CAMPOS_REGISTRADOS:
                _registrar(db, ev, fonte, "alterado", campo, atual, novo)
            if atual != novo_cmp:
                setattr(ev, campo, novo)
                mudou = True
    if b.gratuito is True or (b.preco_max == 0 and b.preco_max is not None):
        if not ev.gratuito:
            ev.gratuito, mudou = True, True
    elif b.preco_min is not None and b.preco_min > 0 and ev.gratuito:
        ev.gratuito, mudou = False, True
    novo_status = status_de(b.status_raw)
    if b.status_raw and novo_status != ev.status and not (ev.status == "encerrado"):
        # um cancelamento/adiamento informado por qualquer fonte vale; "voltou a agendado" só vale se vier da fonte que cancelou/é a dona
        if novo_status in ("cancelado", "adiado", "remarcado") or sobrescrever:
            _registrar(db, ev, fonte, "status", "status", ev.status, novo_status)
            ev.status, mudou = novo_status, True
    if b.data_incerta != ev.data_incerta and (sobrescrever or b.data_incerta is False):
        ev.data_incerta, mudou = b.data_incerta, True
    ev.nome_norm = norm_nome_evento(ev.titulo)
    ev.visto_em = _agora()
    return mudou


def _dict_dedup(db: Session, ev: Evento) -> dict:
    loc = db.get(EventoLocal, ev.local_id) if ev.local_id else None
    org = db.get(EventoOrganizador, ev.organizador_id) if ev.organizador_id else None
    return {"nome_norm": ev.nome_norm or norm_nome_evento(ev.titulo), "inicio": _utc(ev.inicio), "fuso": ev.fuso,
            "local": {"nome_norm": loc.nome_norm if loc else norm_texto(ev.local_nome), "fonte": loc.fonte if loc else "", "fonte_id": loc.fonte_id if loc else "",
                      "lat": ev.lat, "lon": ev.lon}, "organizador_norm": org.nome_norm if org else ""}


def _dict_dedup_bruto(b: EventoBruto, local: EventoLocal | None, fonte: str, org: EventoOrganizador | None) -> dict:
    return {"nome_norm": norm_nome_evento(b.titulo), "inicio": b.inicio, "fuso": b.fuso,
            "local": {"nome_norm": norm_texto(b.local.nome) if b.local else "", "fonte": fonte if (b.local and b.local.fonte_id) else "",
                      "fonte_id": b.local.fonte_id if b.local else "", "lat": b.local.lat if b.local else None, "lon": b.local.lon if b.local else None},
            "organizador_norm": org.nome_norm if org else ""}


def _candidatos(db: Session, b: EventoBruto, fonte: str):
    if b.inicio is None:
        return []
    ini, fim = b.inicio - JANELA_DEDUP, b.inicio + JANELA_DEDUP
    evs = db.scalars(select(Evento).where(Evento.inicio >= ini, Evento.inicio <= fim)).all()
    out = []
    for e in evs:
        mesma_fonte = db.scalar(select(EventoFonteLink.id).where(EventoFonteLink.evento_id == e.id, EventoFonteLink.fonte == fonte))
        if mesma_fonte:     # dois anúncios da MESMA fonte são eventos distintos (ex.: sessões), nunca duplicata
            continue
        out.append(e)
    return out


def _criar(db: Session, b: EventoBruto, fonte: str, local, org, prioridade: int) -> Evento:
    ev = Evento(fonte=fonte, fonte_id=b.fonte_id, titulo=b.titulo, descricao="", status=status_de(b.status_raw), data_incerta=b.data_incerta,
                coletado_em=_agora(), visto_em=_agora(), nome_norm=norm_nome_evento(b.titulo), organizador_id=org.id if org else None,
                gratuito=bool(b.gratuito or (b.preco_max == 0 and b.preco_max is not None)), extra={"prioridade": prioridade, **({"status_original": b.status_raw} if b.status_raw else {})})
    # a linha primária (fonte, fonte_id) é única; se outra linha já usa esse par (não deveria), o link garante a idempotência
    db.add(ev)
    db.flush()
    _aplicar(db, ev, b, fonte, local, True)
    _registrar(db, ev, fonte, "criado", "", "", b.titulo)
    return ev


def _link(db: Session, ev: Evento, b: EventoBruto, fonte: str) -> EventoFonteLink:
    dados = {k: v for k, v in {"status_original": b.status_raw, "preco_min": b.preco_min, "preco_max": b.preco_max, "moeda": b.moeda, **b.extra}.items() if v not in (None, "")}
    lk = db.scalar(select(EventoFonteLink).where(EventoFonteLink.fonte == fonte, EventoFonteLink.fonte_id == b.fonte_id))
    if lk is None:
        lk = EventoFonteLink(evento_id=ev.id, fonte=fonte, fonte_id=b.fonte_id)
        db.add(lk)
    lk.plataforma, lk.url, lk.ingresso_url, lk.visto_em, lk.dados = b.plataforma, b.url, b.ingresso_url, _agora(), dados
    return lk


def ingerir(db: Session, fonte: str, brutos, prioridade: int = 50) -> Resumo:
    """Processa os eventos de UMA fonte. Cada evento é isolado: um registro ruim não derruba o lote."""
    r = Resumo()
    semear_categorias(db)
    for bruto in brutos:
        r.coletados += 1
        b, motivo = validar(bruto)
        if b is None:
            r.descartados += 1
            r.motivos_descarte[motivo] += 1
            continue
        try:
            with db.begin_nested():
                _ingerir_um(db, fonte, b, prioridade, r)
        except Exception as exc:                       # registro com problema inesperado: conta e segue
            r.descartados += 1
            r.motivos_descarte[f"erro interno: {type(exc).__name__}"] += 1
    db.commit()
    return r


def _ingerir_um(db: Session, fonte: str, b: EventoBruto, prioridade: int, r: Resumo) -> None:
    local = obter_local(db, b.local, fonte)
    org = obter_organizador(db, b.organizador, fonte)
    lk = db.scalar(select(EventoFonteLink).where(EventoFonteLink.fonte == fonte, EventoFonteLink.fonte_id == b.fonte_id))
    if lk is not None:                                  # já conhecemos este anúncio: atualiza
        ev = db.get(Evento, lk.evento_id)
        mudou = _aplicar(db, ev, b, fonte, local, True)
        if org and not ev.organizador_id:
            ev.organizador_id = org.id
        _gravar_relacionados(db, ev, b, fonte, local)
        _link(db, ev, b, fonte)
        r.atualizados += 1 if mudou else 0
        r.inalterados += 0 if mudou else 1
        return
    me = _dict_dedup_bruto(b, local, fonte, org)
    melhor, em_revisao = None, []
    for cand in _candidatos(db, b, fonte):
        res = dedup.comparar(me, _dict_dedup(db, cand))
        if res.decisao == "mesmo" and (melhor is None or res.score > melhor[1].score):
            melhor = (cand, res)
        elif res.decisao == "revisar":
            em_revisao.append((cand, res))
    if melhor:                                          # mesmo evento já visto em outra fonte: junta
        ev, res = melhor
        prio_ev = int((ev.extra or {}).get("prioridade", 50))
        _aplicar(db, ev, b, fonte, local, prioridade > prio_ev)
        if org and not ev.organizador_id:
            ev.organizador_id = org.id
        _gravar_relacionados(db, ev, b, fonte, local)
        _link(db, ev, b, fonte)
        _registrar(db, ev, fonte, "mesclado", "fonte", "", f"{fonte}:{b.fonte_id} ({'; '.join(res.motivos)})")
        r.duplicados += 1
        return
    ev = _criar(db, b, fonte, local, org, prioridade)
    if org:
        ev.organizador_id = org.id
    _gravar_relacionados(db, ev, b, fonte, local)
    _link(db, ev, b, fonte)
    r.novos += 1
    for cand, res in em_revisao:                        # indício forte, prova insuficiente: fila de revisão
        a_id, b_id = sorted((cand.id, ev.id))
        if not db.scalar(select(EventoDuplicata.id).where(EventoDuplicata.evento_a_id == a_id, EventoDuplicata.evento_b_id == b_id)):
            db.add(EventoDuplicata(evento_a_id=a_id, evento_b_id=b_id, score=res.score, motivos=res.motivos))
            r.revisao += 1


# ----------------------------------------------------------------------------- ciclo de vida
def ciclo_de_vida(db: Session, agora: datetime | None = None) -> dict:
    """Marca como 'encerrado' o que já passou. Nada é apagado: o histórico fica e a mudança é registrada."""
    agora = agora or _agora()
    n = 0
    for ev in db.scalars(select(Evento).where(Evento.status.in_(("agendado", "adiado", "remarcado")), Evento.inicio.is_not(None), Evento.data_incerta.is_(False))):
        ini = _utc(ev.inicio)
        local = dedup.data_local(ini, ev.fuso)
        so_data = local is not None and local[1] == 0          # 00:00 = hora desconhecida: vale até o fim do dia seguinte de manhã
        fim = _utc(ev.fim) or ini + timedelta(hours=30 if so_data else 8)
        if fim < agora:
            _registrar(db, ev, "sistema", "status", "status", ev.status, "encerrado")
            ev.status = "encerrado"
            n += 1
    db.commit()
    return {"encerrados": n}


def mesclar_eventos(db: Session, mantido_id: int, absorvido_id: int) -> None:
    """Decisão humana: `absorvido` é o mesmo evento que `mantido`. Move links/imagens/artistas/categorias e preenche lacunas;
    o registro absorvido NÃO é apagado (fica com status 'mesclado', fora das listagens, e o histórico registra a decisão)."""
    a, b = db.get(Evento, mantido_id), db.get(Evento, absorvido_id)
    if a is None or b is None or a.id == b.id:
        raise ValueError("eventos inválidos para mesclagem")
    for L in db.scalars(select(EventoFonteLink).where(EventoFonteLink.evento_id == b.id)):
        L.evento_id = a.id
    tem_img = {i.url for i in db.scalars(select(EventoImagem).where(EventoImagem.evento_id == a.id))}
    for i in db.scalars(select(EventoImagem).where(EventoImagem.evento_id == b.id)):
        if i.url in tem_img:
            db.delete(i)                       # duplicata exata da mesma URL (restrição única); a URL continua no evento mantido
        else:
            i.evento_id = a.id
    tem_art = {l.artista_id for l in db.scalars(select(EventoArtistaLink).where(EventoArtistaLink.evento_id == a.id))}
    for l in db.scalars(select(EventoArtistaLink).where(EventoArtistaLink.evento_id == b.id)):
        if l.artista_id in tem_art:
            db.delete(l)
        else:
            l.evento_id = a.id
    tem_cat = {l.categoria_id for l in db.scalars(select(EventoCategoriaLink).where(EventoCategoriaLink.evento_id == a.id))}
    for l in db.scalars(select(EventoCategoriaLink).where(EventoCategoriaLink.evento_id == b.id)):
        if l.categoria_id in tem_cat:
            db.delete(l)
        else:
            l.evento_id, l.primaria = a.id, False
    for campo in ("descricao", "imagem_url", "ingresso_url", "url", "local_id", "organizador_id", "classificacao_indicativa", "acessibilidade", "preco_min", "preco_max", "moeda"):
        if not getattr(a, campo) and getattr(b, campo):
            setattr(a, campo, getattr(b, campo))
    b.status = "mesclado"
    b.extra = {**(b.extra or {}), "mesclado_em_evento_id": a.id}
    _registrar(db, a, "revisao", "mesclado", "evento", "", f"evento {b.id} incorporado por decisão humana")
    db.flush()
