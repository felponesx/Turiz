"""Recarrega data/*.json no banco local (usado pelo workflow e para subir a API do zero)."""
import json
import os
from datetime import datetime
from app.db import Base, SessionLocal, engine
from app.ingest import upsert
from app.models import Evento, Lugar

Base.metadata.create_all(engine)
with SessionLocal() as db:
    for nome, modelo in (("lugares", Lugar), ("eventos", Evento)):
        p = f"data/{nome}.json"
        if os.path.exists(p):
            regs = json.load(open(p, encoding="utf-8"))
            for r in regs:
                for k in ("inicio", "fim"):
                    if r.get(k):
                        r[k] = datetime.fromisoformat(r[k])
                r.pop("id", None)
            print(nome, upsert(db, modelo, regs))
