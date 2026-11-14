"""Carrega data/*.json no banco (usado no startup da API, no workflow e manualmente)."""
import gzip
import json
import os
from datetime import datetime
from .db import Base, SessionLocal, engine
from .ingest import upsert
from .models import Cardapio, Evento, Imagem, Lugar, RedeSocial


def restaurar(pasta="data"):
    from .migrar import upgrade_head
    from .eventos import snapshot
    upgrade_head()
    saida = {}
    with SessionLocal() as db:
        v2 = snapshot.restaurar(db, pasta)           # eventos v2 (com relacionamentos); None se não há snapshot ou o banco já tem eventos
        if v2 is not None:
            saida["eventos_v2"] = v2
        tem_v2 = os.path.exists(os.path.join(pasta, snapshot.ARQUIVO))
        for nome, modelo in (("lugares", Lugar), ("eventos", Evento), ("imagens", Imagem), ("redes_sociais", RedeSocial), ("cardapios", Cardapio)):
            p = os.path.join(pasta, f"{nome}.json")
            if not os.path.exists(p) or (nome == "eventos" and tem_v2):   # com snapshot v2, o legado de eventos é redundante
                continue
            regs = json.load(open(p, encoding="utf-8"))
            for r in regs:
                for k in ("inicio", "fim"):
                    if r.get(k):
                        r[k] = datetime.fromisoformat(r[k])
                r.pop("id", None)
            saida[nome] = upsert(db, modelo, regs)
        # base ampliada (Receita + IBGE): arquivo grande, comprimido. Sem CNPJ (veja app/sources/receita.py).
        p = os.path.join(pasta, "lugares_receita.json.gz")
        if os.path.exists(p):
            with gzip.open(p, "rt", encoding="utf-8") as f:
                regs = json.load(f)
            if db.query(Lugar).filter(Lugar.fonte == "receita").count() == 0:   # banco novo: carga em bloco (rápida)
                db.bulk_insert_mappings(Lugar, regs)
                db.commit()
                saida["lugares_receita"] = {"novos": len(regs), "atualizados": 0}
            else:
                saida["lugares_receita"] = upsert(db, Lugar, regs)
    return saida
