#!/usr/bin/env python3
"""Bot de imagens. Ex.: python coletar_imagens.py commons site [--limite-sites 200]
Guarda referências em data/imagens.json (versionado)."""
import argparse
import json
from datetime import datetime
from sqlalchemy import select
from app.db import Base, SessionLocal, engine
from app.ingest import upsert
from app.models import Imagem, Lugar
from app.restaurar import restaurar
from app.sources import imagens


def exportar(db):
    def d(o):
        return {c.name: (v.isoformat() if isinstance(v := getattr(o, c.name), datetime) else v) for c in o.__table__.columns}
    with open("data/imagens.json", "w", encoding="utf-8") as f:
        json.dump([d(o) for o in db.scalars(select(Imagem).order_by(Imagem.lugar_fonte_id, Imagem.url))], f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fontes", nargs="+", choices=["commons", "site"])
    ap.add_argument("--limite-sites", type=int, default=None, help="máximo de sites a visitar (teste)")
    a = ap.parse_args()
    Base.metadata.create_all(engine)
    restaurar()  # garante lugares e imagens atuais no banco
    falhas = []
    with SessionLocal() as db:
        for f in a.fontes:
            try:
                if f == "commons":
                    print("commons", upsert(db, Imagem, imagens.coletar_commons()))
                else:
                    ls = [{"fonte": l.fonte, "fonte_id": l.fonte_id, "site": l.site} for l in db.scalars(select(Lugar).where(Lugar.site != ""))]
                    regs, stats = imagens.coletar_sites(ls, limite=a.limite_sites)
                    print("site", upsert(db, Imagem, regs), stats)
            except Exception as exc:  # cada fonte é independente
                db.rollback()
                falhas.append(f)
                print(f"::warning::fonte {f} falhou: {type(exc).__name__}: {exc}")
        exportar(db)
        tot = {s: db.query(Imagem).filter(Imagem.status == s).count() for s in ("aprovada", "pendente")}
        print("imagens:", tot, "| falhas:", falhas or "nenhuma")


if __name__ == "__main__":
    main()
