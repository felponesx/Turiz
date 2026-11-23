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
from bots.status import bot


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
    with bot("imagens") as rep:
        _executar(a, rep)


def _executar(a, rep):
    rep.progresso(0, 0, atual="Carregando os dados")
    __import__("app.migrar", fromlist=["x"]).upgrade_head()
    restaurar()  # garante lugares e imagens atuais no banco
    falhas = []
    faixas = {"commons": (0, 15), "site": (15, 100)} if len(a.fontes) > 1 else {a.fontes[0]: (0, 100)}
    with SessionLocal() as db:
        for f in a.fontes:
            try:
                with rep.faixa(*faixas[f]):
                    if f == "commons":
                        rep.progresso(0, 1, atual="Wikimedia Commons", etapa="Fotos livres do Commons")
                        r = upsert(db, Imagem, imagens.coletar_commons())
                        print("commons", r)
                        rep.progresso(1, 1, atual="Wikimedia Commons")
                        rep.contar(novos=r["novos"], atualizados=r["atualizados"])
                    else:
                        ls = [{"fonte": l.fonte, "fonte_id": l.fonte_id, "site": l.site} for l in db.scalars(select(Lugar).where(Lugar.site != ""))]
                        rep.definir(sites_para_visitar=len(ls[:a.limite_sites]))
                        regs, stats = imagens.coletar_sites(ls, limite=a.limite_sites, progresso=rep.callback())
                        r = upsert(db, Imagem, regs)
                        print("site", r, stats)
                        rep.contar(novos=r["novos"], atualizados=r["atualizados"])
            except Exception as exc:  # cada fonte é independente
                db.rollback()
                falhas.append(f)
                rep.aviso(f"fonte {f} falhou: {type(exc).__name__}")
                print(f"::warning::fonte {f} falhou: {type(exc).__name__}: {exc}")
        exportar(db)
        tot = {s: db.query(Imagem).filter(Imagem.status == s).count() for s in ("aprovada", "pendente")}
        rep.total_no_sistema(imagens=sum(tot.values()), lugares_com_imagem=db.query(Imagem.lugar_fonte_id).distinct().count())
        print("imagens:", tot, "| falhas:", falhas or "nenhuma")


if __name__ == "__main__":
    main()
