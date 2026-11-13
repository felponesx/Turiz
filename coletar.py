#!/usr/bin/env python3
"""CLI de coleta. Ex.: python coletar.py osm sites | python coletar.py google --centros -23.55,-46.63
Depois de coletar, exporta snapshot em data/ (versionado no git)."""
import argparse
import json
from datetime import datetime
from sqlalchemy import select
from app.db import Base, SessionLocal, engine
from app.ingest import upsert
from app.models import Evento, Lugar
from app.sources import eventbrite, google_places, osm, sites, ticketmaster, vincular

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
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        falhas = []
        for f in a.fontes:
            try:
                if f == "osm":
                    print("osm", upsert(db, Lugar, osm.coletar()))
                elif f == "google":
                    cs = [tuple(map(float, c.split(","))) for c in a.centros.split(";")] if a.centros else list(centros_padrao())
                    print("google", upsert(db, Lugar, google_places.coletar(cs)))
                elif f == "eventbrite":
                    print("eventbrite", upsert(db, Evento, eventbrite.coletar(a.orgs)))
                elif f == "ticketmaster":
                    print("ticketmaster", upsert(db, Evento, ticketmaster.coletar()))
                elif f == "sites":
                    l, e, ign = sites.coletar()
                    print("sites", upsert(db, Lugar, l), upsert(db, Evento, e), "bloqueados por robots.txt:", ign)
            except Exception as exc:  # cada fonte é independente
                db.rollback()
                falhas.append(f)
                print(f"::warning::fonte {f} falhou: {type(exc).__name__}: {exc}")
        print("vínculo evento->lugar:", vincular.vincular_eventos(db))
        exportar(db)
        print("falhas:", falhas or "nenhuma")


if __name__ == "__main__":
    main()
