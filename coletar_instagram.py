#!/usr/bin/env python3
"""Vincula perfis do Instagram aos lugares (tag do OSM + link no site oficial) e, com credenciais,
verifica pela API oficial. Saída: data/redes_sociais.json
Ex.: python coletar_instagram.py [--limite-sites 100]   (INSTAGRAM_TOKEN e INSTAGRAM_USER_ID opcionais)"""
import argparse
import json
import os
import time
import httpx
from datetime import datetime
from sqlalchemy import select
from app.db import Base, SessionLocal, engine
from app.ingest import upsert
from app.models import Lugar, RedeSocial
from app.restaurar import restaurar
from app.sources import instagram


def exportar(db):
    def d(o):
        return {c.name: (v.isoformat() if isinstance(v := getattr(o, c.name), datetime) else v) for c in o.__table__.columns}
    with open("data/redes_sociais.json", "w", encoding="utf-8") as f:
        json.dump([d(o) for o in db.scalars(select(RedeSocial).order_by(RedeSocial.lugar_fonte_id, RedeSocial.usuario))], f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite-sites", type=int, default=None)
    ap.add_argument("--max-verificacoes", type=int, default=150, help="limite de consultas à API oficial por execução")
    a = ap.parse_args()
    Base.metadata.create_all(engine)
    restaurar()
    token, ig_id = os.getenv("INSTAGRAM_TOKEN"), os.getenv("INSTAGRAM_USER_ID")
    with SessionLocal() as db:
        lugares = [{"fonte": l.fonte, "fonte_id": l.fonte_id, "nome": l.nome, "site": l.site, "extra": l.extra or {}} for l in db.scalars(select(Lugar))]
        # não sobrescrever vínculos já confirmados/rejeitados manualmente
        travados = {(r.lugar_fonte_id, r.usuario) for r in db.scalars(select(RedeSocial).where(RedeSocial.origem == "api_oficial"))}
        novos = [v for l in lugares for v in instagram.vinculos_osm(l)]
        print("osm_tag", upsert(db, RedeSocial, [v for v in novos if (v["lugar_fonte_id"], v["usuario"]) not in travados]))
        try:
            regs, stats = instagram.vinculos_sites([l for l in lugares if l["site"]], limite=a.limite_sites)
            print("site", upsert(db, RedeSocial, [v for v in regs if (v["lugar_fonte_id"], v["usuario"]) not in travados]), stats)
        except Exception as exc:
            db.rollback()
            print(f"::warning::sites falhou: {type(exc).__name__}: {exc}")
        if token and ig_id:
            cli = httpx.Client(timeout=30)
            por_id = {l["fonte_id"]: l for l in lugares}
            ok = nao = 0
            pend = [r for r in db.scalars(select(RedeSocial).where(RedeSocial.origem != "api_oficial", RedeSocial.status != "rejeitado"))
                    if not (r.extra or {}).get("verificado")]
            for r in pend[:a.max_verificacoes]:
                l = por_id.get(r.lugar_fonte_id, {})
                try:
                    v = instagram.verificar(r.usuario, l.get("nome", ""), l.get("site", ""), token, ig_id, cli)
                except httpx.HTTPError as exc:
                    print(f"::warning::verificação parou: {exc}")
                    break
                r.extra = {**(r.extra or {}), "verificado": True, "profissional": v is not None}
                if v:
                    r.nome_perfil, r.seguidores = v["nome_perfil"], v["seguidores"]
                    r.extra = {**r.extra, "similaridade": v["similaridade"], "site_confere": v["site_confere"]}
                    if v["confere"]:
                        r.status, r.confianca = "confirmado", 0.98
                    ok += 1
                else:
                    nao += 1
                time.sleep(1)
            db.commit()
            print(f"verificação oficial: {ok} contas profissionais, {nao} sem dados")
        else:
            print("sem INSTAGRAM_TOKEN/INSTAGRAM_USER_ID: pulando verificação pela API oficial")
        exportar(db)
        tot = {s: db.query(RedeSocial).filter(RedeSocial.status == s).count() for s in ("confirmado", "provavel")}
        print("vínculos:", tot, "| lugares com Instagram:", db.query(RedeSocial.lugar_fonte_id).distinct().count())


if __name__ == "__main__":
    main()
