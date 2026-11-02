import os
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from . import ingest
from .restaurar import restaurar
from .db import Base, engine, get_db
from .models import Evento, Imagem, Lugar

Base.metadata.create_all(engine)
app = FastAPI(title="Turiz API", description="Restaurantes, bares e eventos de São Paulo")


@app.on_event("startup")
def carregar_dados_iniciais():
    """Se o banco estiver vazio, carrega os snapshots versionados em data/."""
    from .db import SessionLocal
    with SessionLocal() as db:
        vazio = db.scalar(select(func.count(Lugar.id))) == 0
    if vazio:
        restaurar()


def exigir_chave(x_api_key: str | None = Header(default=None)):
    esperada = os.getenv("API_KEY")
    if not esperada or x_api_key != esperada:
        raise HTTPException(401, "API key inválida")


def lugar_dict(l: Lugar):
    return {c.name: getattr(l, c.name) for c in Lugar.__table__.columns}


def evento_dict(e: Evento):
    return {c.name: getattr(e, c.name) for c in Evento.__table__.columns}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    return {"ok": True, "lugares": db.scalar(select(func.count(Lugar.id))), "eventos": db.scalar(select(func.count(Evento.id)))}


@app.get("/lugares")
def lugares(tipo: str | None = Query(None, pattern="^(restaurante|bar)$"), q: str | None = None,
            bairro: str | None = None, culinaria: str | None = None, fonte: str | None = None,
            limit: int = Query(50, le=500), offset: int = 0, db: Session = Depends(get_db)):
    st = select(Lugar)
    if tipo: st = st.where(Lugar.tipo == tipo)
    if q: st = st.where(Lugar.nome.ilike(f"%{q}%"))
    if bairro: st = st.where(Lugar.bairro.ilike(f"%{bairro}%"))
    if culinaria: st = st.where(Lugar.culinaria.ilike(f"%{culinaria}%"))
    if fonte: st = st.where(Lugar.fonte == fonte)
    total = db.scalar(select(func.count()).select_from(st.subquery()))
    itens = db.scalars(st.order_by(Lugar.nome).limit(limit).offset(offset)).all()
    return {"total": total, "itens": [lugar_dict(i) for i in itens]}


@app.get("/lugares/geo")
def lugares_geo(tipo: str | None = Query(None, pattern="^(restaurante|bar)$"), db: Session = Depends(get_db)):
    """Lista compacta [id, nome, tipo, lat, lon] para desenhar o mapa."""
    st = select(Lugar.id, Lugar.nome, Lugar.tipo, Lugar.lat, Lugar.lon).where(Lugar.lat.is_not(None))
    if tipo: st = st.where(Lugar.tipo == tipo)
    return [list(r) for r in db.execute(st)]


@app.get("/lugares/{lugar_id}")
def lugar(lugar_id: int, db: Session = Depends(get_db)):
    l = db.get(Lugar, lugar_id)
    if not l:
        raise HTTPException(404, "Não encontrado")
    return lugar_dict(l)


@app.get("/lugares/{lugar_id}/imagens")
def imagens_do_lugar(lugar_id: int, status: str = Query("aprovada", pattern="^(aprovada|pendente|todas)$"), db: Session = Depends(get_db)):
    """Imagens de um lugar. Por padrão só as de licença livre identificada (status=aprovada)."""
    l = db.get(Lugar, lugar_id)
    if not l:
        raise HTTPException(404, "Não encontrado")
    st = select(Imagem).where(Imagem.lugar_fonte == l.fonte, Imagem.lugar_fonte_id == l.fonte_id)
    if status != "todas":
        st = st.where(Imagem.status == status)
    return [{c.name: getattr(i, c.name) for c in Imagem.__table__.columns} for i in db.scalars(st)]


@app.patch("/imagens/{imagem_id}", dependencies=[Depends(exigir_chave)])
def moderar_imagem(imagem_id: int, status: str = Query(..., pattern="^(aprovada|pendente|rejeitada)$"), db: Session = Depends(get_db)):
    """Moderação: aprova (você tem permissão/licença) ou rejeita uma imagem."""
    i = db.get(Imagem, imagem_id)
    if not i:
        raise HTTPException(404, "Não encontrada")
    i.status = status
    db.commit()
    return {"id": i.id, "status": i.status}


@app.get("/eventos")
def eventos(q: str | None = None, a_partir_de: datetime | None = None, fonte: str | None = None,
            limit: int = Query(50, le=500), offset: int = 0, db: Session = Depends(get_db)):
    st = select(Evento)
    if q: st = st.where(Evento.titulo.ilike(f"%{q}%"))
    st = st.where(Evento.inicio >= (a_partir_de or datetime.now(timezone.utc)))
    if fonte: st = st.where(Evento.fonte == fonte)
    total = db.scalar(select(func.count()).select_from(st.subquery()))
    itens = db.scalars(st.order_by(Evento.inicio).limit(limit).offset(offset)).all()
    return {"total": total, "itens": [evento_dict(i) for i in itens]}


@app.post("/ingest/lugares", dependencies=[Depends(exigir_chave)])
def ingest_lugares(registros: list[dict], db: Session = Depends(get_db)):
    """Permite que os bots enviem lugares já normalizados."""
    return ingest.upsert(db, Lugar, registros)


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")
