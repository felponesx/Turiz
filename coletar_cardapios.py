#!/usr/bin/env python3
"""Bot de cardápios. Ex.: python coletar_cardapios.py [--limite-sites 200]
Procura o cardápio oficial no site de cada lugar e guarda a referência em data/cardapios.json (versionado)."""
import argparse
import json
from datetime import datetime
from sqlalchemy import select
from app.db import Base, SessionLocal, engine
from app.ingest import upsert
from app.models import Cardapio, Lugar
from app.restaurar import restaurar
from app.sources import cardapios


def exportar(db):
    def d(o):
        return {c.name: (v.isoformat() if isinstance(v := getattr(o, c.name), datetime) else v) for c in o.__table__.columns}
    with open("data/cardapios.json", "w", encoding="utf-8") as f:
        json.dump([d(o) for o in db.scalars(select(Cardapio).order_by(Cardapio.lugar_fonte_id, Cardapio.url))], f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite-sites", type=int, default=None, help="máximo de sites a visitar (teste)")
    ap.add_argument("--dry-run", action="store_true", help="só mede quantos lugares têm cardápio; não grava nada")
    a = ap.parse_args()
    __import__("app.migrar", fromlist=["x"]).upgrade_head()
    restaurar()  # garante lugares e cardápios atuais no banco
    with SessionLocal() as db:
        ls = []
        for l in db.scalars(select(Lugar)):
            menu = (l.extra or {}).get("website:menu") or (l.extra or {}).get("menu:url") or ""
            if l.site or menu:
                ls.append({"fonte": l.fonte, "fonte_id": l.fonte_id, "site": l.site, "menu_osm": menu})
        regs, stats = cardapios.coletar(ls, limite=a.limite_sites)
        if a.dry_run:
            print("DRY-RUN", {**stats, "motivos_sem_resposta": dict(stats["motivos_sem_resposta"])}, "| plataformas:", {p: sum(1 for r in regs if r["plataforma"] == p) for p in sorted({r["plataforma"] for r in regs})},
                  "| com itens (JSON-LD):", sum(1 for r in regs if r["itens"]))
            return
        print("cardapios", upsert(db, Cardapio, regs), {**stats, "motivos_sem_resposta": dict(stats["motivos_sem_resposta"])})
        exportar(db)
        tot = {s: db.query(Cardapio).filter(Cardapio.status == s).count() for s in ("confirmado", "provavel")}
        print("cardapios no banco:", tot)


if __name__ == "__main__":
    main()
