"""Upsert de registros normalizados no banco."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Lugar, Evento

_CAMPOS = {Lugar: {c.name for c in Lugar.__table__.columns} - {"id", "atualizado_em"},
           Evento: {c.name for c in Evento.__table__.columns} - {"id", "atualizado_em"}}


def upsert(db: Session, modelo, registros: list[dict]) -> dict:
    novos = atualizados = 0
    for r in registros:
        r = {k: v for k, v in r.items() if k in _CAMPOS[modelo]}
        obj = db.scalar(select(modelo).where(modelo.fonte == r["fonte"], modelo.fonte_id == r["fonte_id"]))
        if obj is None:
            db.add(modelo(**r))
            novos += 1
        else:
            for k, v in r.items():
                setattr(obj, k, v)
            atualizados += 1
    db.commit()
    return {"novos": novos, "atualizados": atualizados}
