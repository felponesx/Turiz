#!/usr/bin/env python3
"""Completa bairro/CEP/rua dos lugares via Nominatim (1 req/s). Retomável: marca extra.nominatim.
Ex.: python coletar_enderecos.py --max-minutos 150"""
import argparse
import time
import httpx
from sqlalchemy import select
from app.db import Base, SessionLocal, engine
from app.models import Lugar
from app.restaurar import restaurar
from app.sources import enderecos
from coletar import exportar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minutos", type=float, default=150)
    ap.add_argument("--limite", type=int, default=None, help="máximo de lugares (teste)")
    a = ap.parse_args()
    Base.metadata.create_all(engine)
    restaurar()
    fim = time.time() + a.max_minutos * 60
    cli = enderecos.novo_cliente()
    feitos = alterados = erros = 0
    with SessionLocal() as db:
        pendentes = [l for l in db.scalars(select(Lugar).order_by(Lugar.id))
                     if not (l.extra or {}).get("nominatim") and l.lat is not None and (not l.bairro or not l.cep or not l.endereco)]
        print(f"pendentes: {len(pendentes)}")
        for l in pendentes[:a.limite]:
            if time.time() > fim:
                print("tempo máximo atingido; o restante fica para a próxima execução")
                break
            try:
                dados = enderecos.reverso(l.lat, l.lon, cli)
            except httpx.HTTPError as exc:
                erros += 1
                print(f"::warning::{l.fonte_id}: {exc}")
                if erros >= 20:
                    print("muitos erros seguidos; parando")
                    break
                time.sleep(5)
                continue
            erros = 0
            alterados += enderecos.aplicar(l, dados)
            l.extra = {**(l.extra or {}), "nominatim": "ok"}
            feitos += 1
            if feitos % 200 == 0:
                db.commit()
                print(f"  {feitos} consultados, {alterados} completados")
            time.sleep(enderecos.PAUSA)
        db.commit()
        exportar(db)
        total = db.query(Lugar).count()
        print(f"consultados: {feitos} | completados: {alterados}")
        print(f"bairro: {db.query(Lugar).filter(Lugar.bairro != '').count()}/{total} | cep: {db.query(Lugar).filter(Lugar.cep != '').count()}/{total} | rua: {db.query(Lugar).filter(Lugar.endereco != '').count()}/{total}")


if __name__ == "__main__":
    main()
