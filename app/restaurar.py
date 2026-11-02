"""Carrega data/*.json no banco (usado no startup da API, no workflow e manualmente)."""
import json
import os
from datetime import datetime
from .db import Base, SessionLocal, engine
from .ingest import upsert
from .models import Evento, Imagem, Lugar


def restaurar(pasta="data"):
    Base.metadata.create_all(engine)
    saida = {}
    with SessionLocal() as db:
        for nome, modelo in (("lugares", Lugar), ("eventos", Evento), ("imagens", Imagem)):
            p = os.path.join(pasta, f"{nome}.json")
            if not os.path.exists(p):
                continue
            regs = json.load(open(p, encoding="utf-8"))
            for r in regs:
                for k in ("inicio", "fim"):
                    if r.get(k):
                        r[k] = datetime.fromisoformat(r[k])
                r.pop("id", None)
            saida[nome] = upsert(db, modelo, regs)
    return saida
