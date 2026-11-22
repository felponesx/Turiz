import os
import re
import threading
import time
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from . import ingest
from .restaurar import restaurar
from .db import Base, engine, get_db
from pydantic import BaseModel, Field
from .models import Avaliacao, Cardapio, Evento, Imagem, Lugar, RedeSocial
from .sources import horarios as hor
from .seguranca import chaves as _chaves, config as _cfg
from .seguranca.chaves import exigir_chave, exigir_escopo
from .seguranca.entrada import IdPositivo, LIKE_ESCAPE, like
from .seguranca.middleware import SegurancaMiddleware

from .migrar import upgrade_head
upgrade_head()          # esquema versionado (Alembic); bancos antigos são marcados e atualizados sem perder dados
_docs = _cfg.docs_ligados()
app = FastAPI(title="Turiz API", description="Restaurantes, bares e eventos de São Paulo",
              docs_url="/docs" if _docs else None, redoc_url=None, openapi_url="/openapi.json" if _docs else None)
_chaves.carregar()          # falha na partida (em produção) se alguma chave for fraca ou malformada
if _cfg.hosts_permitidos():
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_cfg.hosts_permitidos())
if _cfg.origens_cors():          # CORS só para as origens listadas; por padrão nenhuma
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=_cfg.origens_cors(), allow_methods=["GET"], allow_headers=["Content-Type"], max_age=600)
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402


@app.exception_handler(RequestValidationError)
async def validacao_sem_eco(request, exc):
    """422 sem devolver o que o cliente enviou (evita ecoar senhas/dados em respostas, logs de proxy e caches)."""
    return JSONResponse(status_code=422, content={"detail": [{"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in exc.errors()]})


app.add_middleware(SegurancaMiddleware)          # por último = mais externa: protege tudo que vem depois


@app.on_event("startup")
def carregar_dados_iniciais():
    """Se o banco estiver vazio, carrega os snapshots versionados em data/."""
    from .db import SessionLocal
    with SessionLocal() as db:
        vazio = db.scalar(select(func.count(Lugar.id))) == 0
    if vazio:
        restaurar()


def lugar_dict(l: Lugar):
    return {c.name: getattr(l, c.name) for c in Lugar.__table__.columns}


def evento_dict(e: Evento):
    return {c.name: getattr(e, c.name) for c in Evento.__table__.columns}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Público e mínimo (monitoramento externo). Contagens e detalhes ficam em /admin/saude."""
    db.scalar(select(func.count(Lugar.id)).where(Lugar.id == 0))
    return {"ok": True}


@app.get("/admin/saude", dependencies=[Depends(exigir_escopo("moderacao"))])
def saude_detalhada(db: Session = Depends(get_db)):
    return {"ok": True, "lugares": db.scalar(select(func.count(Lugar.id))), "eventos": db.scalar(select(func.count(Evento.id))),
            "cardapios": db.scalar(select(func.count(Cardapio.id))), "imagens": db.scalar(select(func.count(Imagem.id))),
            "avaliacoes": db.scalar(select(func.count(Avaliacao.id)).where(Avaliacao.status == "publicada"))}


def _ids_por_abertura(db, aberto: bool) -> list[int]:
    ids = []
    for i, h in db.execute(select(Lugar.id, Lugar.horario).where(Lugar.horario != "")):
        r = hor.aberto_agora(hor.parse(h))
        if r is not None and r == aberto:
            ids.append(i)
    return ids


@app.get("/lugares")
def lugares(tipo: str | None = Query(None, pattern="^(restaurante|bar)$"), q: str | None = None,
            bairro: str | None = None, culinaria: str | None = None, fonte: str | None = None,
            aberto_agora: bool | None = Query(None, description="só quem tem horário interpretável: true=aberto, false=fechado"),
            limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0, le=100_000), db: Session = Depends(get_db)):
    st = select(Lugar)
    if aberto_agora is not None:
        st = st.where(Lugar.id.in_(_ids_por_abertura(db, aberto_agora)))
    if tipo: st = st.where(Lugar.tipo == tipo)
    if q: st = st.where(Lugar.nome.ilike(like(q), escape=LIKE_ESCAPE))
    if bairro: st = st.where(Lugar.bairro.ilike(like(bairro), escape=LIKE_ESCAPE))
    if culinaria: st = st.where(Lugar.culinaria.ilike(like(culinaria), escape=LIKE_ESCAPE))
    if fonte: st = st.where(Lugar.fonte == fonte)
    total = db.scalar(select(func.count()).select_from(st.subquery()))
    itens = db.scalars(st.order_by(Lugar.nome).limit(limit).offset(offset)).all()
    return {"total": total, "itens": [lugar_dict(i) for i in itens]}


_GEO: dict = {}
_GEO_LOCK = threading.Lock()


@app.get("/lugares/geo")
def lugares_geo(response: Response, tipo: str | None = Query(None, pattern="^(restaurante|bar)$"), db: Session = Depends(get_db)):
    """Lista compacta [id, nome, tipo, lat, lon] para desenhar o mapa. Rota cara: cache de 5 min no servidor e no navegador/CDN."""
    agora = time.monotonic()
    with _GEO_LOCK:
        hit = _GEO.get(tipo)
        if hit and agora - hit[0] < 300:
            response.headers["Cache-Control"] = "public, max-age=300"
            return hit[1]
    st = select(Lugar.id, Lugar.nome, Lugar.tipo, Lugar.lat, Lugar.lon).where(Lugar.lat.is_not(None))
    if tipo: st = st.where(Lugar.tipo == tipo)
    dados = [list(r) for r in db.execute(st)]
    with _GEO_LOCK:
        _GEO[tipo] = (agora, dados)
    response.headers["Cache-Control"] = "public, max-age=300"
    return dados


@app.get("/lugares/{lugar_id}")
def lugar(lugar_id: IdPositivo, db: Session = Depends(get_db)):
    l = db.get(Lugar, lugar_id)
    if not l:
        raise HTTPException(404, "Não encontrado")
    h = hor.parse(l.horario)
    return {**lugar_dict(l), "horario_estruturado": h, "aberto_agora": hor.aberto_agora(h)}


def _lugar_ou_404(db, lugar_id: int) -> Lugar:
    l = db.get(Lugar, lugar_id)
    if not l:
        raise HTTPException(404, "Não encontrado")
    return l


@app.get("/lugares/{lugar_id}/cardapios")
def cardapios_do_lugar(lugar_id: IdPositivo, db: Session = Depends(get_db)):
    """Cardápios oficiais do lugar (link e, quando o site publica, itens e preços)."""
    l = _lugar_ou_404(db, lugar_id)
    st = select(Cardapio).where(Cardapio.lugar_fonte == l.fonte, Cardapio.lugar_fonte_id == l.fonte_id, Cardapio.status != "rejeitado")
    return [{c.name: getattr(x, c.name) for c in Cardapio.__table__.columns} for x in db.scalars(st.order_by(Cardapio.status))]


@app.get("/lugares/{lugar_id}/eventos")
def eventos_do_lugar(lugar_id: IdPositivo, db: Session = Depends(get_db)):
    """Próximos eventos que acontecem neste lugar (vínculo feito por distância e nome)."""
    l = _lugar_ou_404(db, lugar_id)
    st = select(Evento).where(Evento.lugar_fonte == l.fonte, Evento.lugar_fonte_id == l.fonte_id,
                              Evento.inicio >= datetime.now(timezone.utc)).order_by(Evento.inicio)
    return [evento_dict(e) for e in db.scalars(st)]


class NovaAvaliacao(BaseModel):
    lugar_id: int
    experiencia_ref: str = Field(min_length=1, max_length=80)
    autor_ref: str = Field(default="", max_length=80)
    nota_comida: int = Field(ge=1, le=5)
    nota_ambiente: int = Field(ge=1, le=5)
    nota_atendimento: int = Field(ge=1, le=5)
    comentario: str = Field(default="", max_length=1000)
    validada: bool = False


@app.post("/avaliacoes", dependencies=[Depends(exigir_escopo("ingest"))], status_code=201)
def criar_avaliacao(a: NovaAvaliacao, db: Session = Depends(get_db)):
    """O backend do app envia a avaliação depois de uma experiência. Só entra publicada se validada por nota fiscal."""
    l = _lugar_ou_404(db, a.lugar_id)
    if db.scalar(select(Avaliacao).where(Avaliacao.experiencia_ref == a.experiencia_ref)):
        raise HTTPException(409, "Esta experiência já foi avaliada")
    av = Avaliacao(lugar_fonte=l.fonte, lugar_fonte_id=l.fonte_id, experiencia_ref=a.experiencia_ref, autor_ref=a.autor_ref,
                   nota_comida=a.nota_comida, nota_ambiente=a.nota_ambiente, nota_atendimento=a.nota_atendimento,
                   comentario=a.comentario, validada=a.validada, status="publicada" if a.validada else "pendente")
    db.add(av)
    db.commit()
    return {"id": av.id, "status": av.status}


@app.patch("/avaliacoes/{avaliacao_id}", dependencies=[Depends(exigir_escopo("moderacao"))])
def moderar_avaliacao(avaliacao_id: IdPositivo, status: str = Query(..., pattern="^(publicada|pendente|rejeitada)$"), db: Session = Depends(get_db)):
    av = db.get(Avaliacao, avaliacao_id)
    if not av:
        raise HTTPException(404, "Não encontrada")
    av.status = status
    db.commit()
    return {"id": av.id, "status": av.status}


@app.get("/lugares/{lugar_id}/avaliacoes")
def avaliacoes_do_lugar(lugar_id: IdPositivo, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=10_000), db: Session = Depends(get_db)):
    """Avaliações publicadas do TURIZ + resumo (média, total, distribuição). Sem nota = ainda não avaliado."""
    l = _lugar_ou_404(db, lugar_id)
    base = (Avaliacao.lugar_fonte == l.fonte, Avaliacao.lugar_fonte_id == l.fonte_id, Avaliacao.status == "publicada")
    n, mc, ma, mt = db.execute(select(func.count(), func.avg(Avaliacao.nota_comida), func.avg(Avaliacao.nota_ambiente), func.avg(Avaliacao.nota_atendimento)).where(*base)).one()
    media = lambda v: round(float(v), 2) if n else None
    dist = {str(k): 0 for k in range(5, 0, -1)}
    for nota, qtd in db.execute(select(func.round((Avaliacao.nota_comida + Avaliacao.nota_ambiente + Avaliacao.nota_atendimento) / 3.0), func.count()).where(*base).group_by(
            func.round((Avaliacao.nota_comida + Avaliacao.nota_ambiente + Avaliacao.nota_atendimento) / 3.0))):
        dist[str(int(nota))] += qtd
    itens = db.scalars(select(Avaliacao).where(*base).order_by(Avaliacao.criado_em.desc()).limit(limit).offset(offset))
    return {"resumo": {"total": n, "nota": round((media(mc) + media(ma) + media(mt)) / 3, 2) if n else None,
                       "comida": media(mc), "ambiente": media(ma), "atendimento": media(mt),
                       "distribuicao": dist},
            "itens": [{"id": a.id, "nota_comida": a.nota_comida, "nota_ambiente": a.nota_ambiente, "nota_atendimento": a.nota_atendimento,
                       "comentario": a.comentario, "validada": a.validada, "criado_em": a.criado_em} for a in itens]}


@app.get("/lugares/{lugar_id}/imagens")
def imagens_do_lugar(lugar_id: IdPositivo, status: str = Query("aprovada", pattern="^(aprovada|pendente|todas)$"), db: Session = Depends(get_db)):
    """Imagens de um lugar. Por padrão só as de licença livre identificada (status=aprovada)."""
    l = db.get(Lugar, lugar_id)
    if not l:
        raise HTTPException(404, "Não encontrado")
    st = select(Imagem).where(Imagem.lugar_fonte == l.fonte, Imagem.lugar_fonte_id == l.fonte_id)
    if status != "todas":
        st = st.where(Imagem.status == status)
    return [{c.name: getattr(i, c.name) for c in Imagem.__table__.columns} for i in db.scalars(st)]


@app.patch("/imagens/{imagem_id}", dependencies=[Depends(exigir_escopo("moderacao"))])
def moderar_imagem(imagem_id: IdPositivo, status: str = Query(..., pattern="^(aprovada|pendente|rejeitada)$"), db: Session = Depends(get_db)):
    """Moderação: aprova (você tem permissão/licença) ou rejeita uma imagem."""
    i = db.get(Imagem, imagem_id)
    if not i:
        raise HTTPException(404, "Não encontrada")
    i.status = status
    db.commit()
    return {"id": i.id, "status": i.status}


@app.get("/lugares/{lugar_id}/redes")
def redes_do_lugar(lugar_id: IdPositivo, db: Session = Depends(get_db)):
    """Perfis de rede social (Instagram) vinculados ao lugar, com origem e confiança."""
    l = db.get(Lugar, lugar_id)
    if not l:
        raise HTTPException(404, "Não encontrado")
    st = select(RedeSocial).where(RedeSocial.lugar_fonte == l.fonte, RedeSocial.lugar_fonte_id == l.fonte_id,
                                  RedeSocial.status != "rejeitado").order_by(RedeSocial.confianca.desc())
    return [{c.name: getattr(r, c.name) for c in RedeSocial.__table__.columns} for r in db.scalars(st)]


@app.post("/ingest/lugares", dependencies=[Depends(exigir_escopo("ingest"))])
def ingest_lugares(registros: list[dict], db: Session = Depends(get_db)):
    """Permite que os bots enviem lugares já normalizados. Lote limitado, campos validados, URLs só http(s)."""
    if len(registros) > _cfg.max_itens_ingest():
        raise HTTPException(413, f"Lote grande demais (máx. {_cfg.max_itens_ingest()} registros)")
    limpos = []
    for r in registros:
        if not isinstance(r.get("fonte"), str) or not isinstance(r.get("fonte_id"), str) or not r["fonte"] or not r["fonte_id"] \
                or len(r["fonte"]) > 30 or len(r["fonte_id"]) > 200:
            raise HTTPException(422, "Cada registro precisa de 'fonte' (até 30) e 'fonte_id' (até 200 caracteres)")
        r = {k: (v[:600] if isinstance(v, str) else v) for k, v in r.items()}
        if r.get("site") and not re.match(r"^https?://[^\s<>\"']+$", r["site"]):
            r["site"] = ""                         # nunca guardamos javascript:, data: etc. em links
        limpos.append(r)
    return ingest.upsert(db, Lugar, limpos)


from .eventos.api import criar_router
from .conta.api import router as conta_router
app.include_router(criar_router(exigir_chave))
app.include_router(conta_router)

app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")
