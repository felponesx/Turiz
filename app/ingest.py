"""Upsert de registros normalizados no banco."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Lugar, Evento, Imagem, RedeSocial

_CAMPOS = {Lugar: {c.name for c in Lugar.__table__.columns} - {"id", "atualizado_em"},
           Evento: {c.name for c in Evento.__table__.columns} - {"id", "atualizado_em"},
           Imagem: {c.name for c in Imagem.__table__.columns} - {"id", "atualizado_em"},
           RedeSocial: {c.name for c in RedeSocial.__table__.columns} - {"id", "atualizado_em"}}


def upsert(db: Session, modelo, registros: list[dict]) -> dict:
    novos = atualizados = 0
    for r in registros:
        r = {k: v for k, v in r.items() if k in _CAMPOS[modelo]}
        if modelo is Imagem:
            cond = (Imagem.lugar_fonte == r["lugar_fonte"], Imagem.lugar_fonte_id == r["lugar_fonte_id"], Imagem.url == r["url"])
        elif modelo is RedeSocial:
            cond = (RedeSocial.lugar_fonte == r["lugar_fonte"], RedeSocial.lugar_fonte_id == r["lugar_fonte_id"],
                    RedeSocial.rede == r.get("rede", "instagram"), RedeSocial.usuario == r["usuario"])
        else:
            cond = (modelo.fonte == r["fonte"], modelo.fonte_id == r["fonte_id"])
        obj = db.scalar(select(modelo).where(*cond))
        if obj is None:
            db.add(modelo(**r))
            novos += 1
        else:
            for k, v in r.items():
                setattr(obj, k, v)
            atualizados += 1
    db.commit()
    return {"novos": novos, "atualizados": atualizados}
