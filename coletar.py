#!/usr/bin/env python3
"""CLI de coleta. Ex.: python coletar.py osm sites | python coletar.py google --centros -23.55,-46.63
Depois de coletar, exporta snapshot em data/ (versionado no git)."""
import argparse
import contextlib
import json
import os
from datetime import datetime
import httpx
from sqlalchemy import select
from app.db import Base, SessionLocal, engine
from app.ingest import upsert
from app.models import Evento, Lugar
from app.sources import eventbrite, google_places, osm, sites, ticketmaster, vincular
from bots.status import Pular, aguardar_credencial, bot, pausado, registrar_pausa

# Centros aproximados para varrer SP no Google (raio de 1,5 km cada ~ grade de 3 km).
def centros_padrao():
    s, w, n, e = osm.BBOX_SP
    lat = s
    while lat < n:
        lon = w
        while lon < e:
            yield (round(lat, 4), round(lon, 4))
            lon += 0.03
        lat += 0.03


def exportar(db):
    from app.eventos import snapshot
    snapshot.exportar(db)
    def d(o):
        return {c.name: (v.isoformat() if isinstance(v := getattr(o, c.name), datetime) else v) for c in o.__table__.columns}
    for nome, modelo in (("lugares", Lugar), ("eventos", Evento)):
        with open(f"data/{nome}.json", "w", encoding="utf-8") as f:
            json.dump([d(o) for o in db.scalars(select(modelo).order_by(modelo.id))], f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fontes", nargs="+", choices=["osm", "google", "eventbrite", "sites", "ticketmaster"])
    ap.add_argument("--centros", help="lat,lon;lat,lon (Google). Padrão: grade de SP")
    ap.add_argument("--orgs", nargs="*", default=[], help="IDs de organização Eventbrite")
    a = ap.parse_args()
    __import__("app.migrar", fromlist=["x"]).upgrade_head()
    with SessionLocal() as db:
        falhas = []
        for f in a.fontes:
            if f in ("osm", "sites", "google"):
                em_pausa, motivo = pausado(f)
                if em_pausa:                       # pausa do Core: pula só esta fonte e segue com as outras
                    registrar_pausa(f, motivo)
                    continue
            try:
                with (bot(f, verificar_pausa=False) if f in ("osm", "sites", "google") else contextlib.nullcontext()) as rep:
                    cb = rep.callback() if rep else None
                    _fonte(f, a, db, rep, cb)
            except Exception as exc:  # cada fonte é independente
                db.rollback()
                falhas.append(f)
                print(f"::warning::fonte {f} falhou: {type(exc).__name__}: {exc}")
        print("vínculo evento->lugar:", vincular.vincular_eventos(db))
        exportar(db)
        print("falhas:", falhas or "nenhuma")


def _fonte(f, a, db, rep, cb):
    if f == "osm":
        regioes_ruins = []
        r = upsert(db, Lugar, osm.coletar(progresso=cb, falhas=regioes_ruins))
        print("osm", r)
        if regioes_ruins:
            rep.aviso(f"{len(regioes_ruins)} região(ões) sem resposta do Overpass ({', '.join(map(str, regioes_ruins))}); entram na próxima coleta")
        rep.contar(novos=r["novos"], atualizados=r["atualizados"])
        rep.total_no_sistema(lugares=db.query(Lugar).count())
    elif f == "google":
        if not os.getenv("GOOGLE_PLACES_API_KEY"):
            aguardar_credencial("GOOGLE_PLACES_API_KEY")
        cs = [tuple(map(float, c.split(","))) for c in a.centros.split(";")] if a.centros else list(centros_padrao())
        try:
            regs = google_places.coletar(cs, progresso=cb)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (400, 401, 403):
                raise Pular("aguardando_credencial", f"O Google recusou a chave (HTTP {exc.response.status_code}): ative a Places API (New) e o faturamento no projeto da chave.")
            raise
        r = upsert(db, Lugar, regs)
        print("google", r)
        rep.contar(novos=r["novos"], atualizados=r["atualizados"])
        rep.total_no_sistema(lugares=db.query(Lugar).count())
    elif f == "eventbrite":
        print("eventbrite", upsert(db, Evento, eventbrite.coletar(a.orgs)))
    elif f == "ticketmaster":   # agora pelo sistema de eventos v2 (conector, deduplicação, histórico)
        from app.eventos import agendador
        agendador.sincronizar_fontes(db)
        print("ticketmaster", [(l.status, l.novos, l.mensagem) for l in agendador.executar_devidas(db, apenas=["ticketmaster"], forcar=True)])
    elif f == "sites":          # lugares (JSON-LD) aqui; os EVENTOS de sites vêm das fontes jsonld de fontes_eventos.yml
        l, e, ign = sites.coletar(progresso=cb)
        r = upsert(db, Lugar, l)
        print("sites", r, "eventos ficam com coletar_eventos.py; bloqueados por robots.txt:", ign)
        rep.contar(novos=r["novos"], atualizados=r["atualizados"], bloqueados=len(ign))
        rep.total_no_sistema(lugares=db.query(Lugar).count())


if __name__ == "__main__":
    main()
