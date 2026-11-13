"""Ticketmaster Discovery API (opcional): shows e eventos grandes de São Paulo.

Precisa de TICKETMASTER_API_KEY (chave gratuita em developer.ticketmaster.com). Sem a chave, a fonte é ignorada.
Os eventos trazem sempre o link oficial de compra (`ingresso_url`); mostre o link junto. Leia os termos de uso da API
antes de republicar os dados: este coletor só roda quando você inclui `ticketmaster` nas fontes.
"""
import os
import time
from datetime import datetime
import httpx

API = "https://app.ticketmaster.com/discovery/v2/events.json"
CENTRO_SP = "-23.5505,-46.6333"


def _data(d: dict):
    s = (d.get("start") or {}).get("dateTime")
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None
    except ValueError:
        return None


def normalizar(ev: dict) -> dict | None:
    if not ev.get("id") or not ev.get("name"):
        return None
    v = ((ev.get("_embedded") or {}).get("venues") or [{}])[0]
    loc = v.get("location") or {}
    cls = (ev.get("classifications") or [{}])[0]
    cat = ((cls.get("segment") or {}).get("name") or "").lower()
    cat = {"music": "musica", "arts & theatre": "teatro", "sports": "esporte", "film": "cinema"}.get(cat, cat or "evento")
    imgs = sorted((i for i in ev.get("images") or [] if i.get("url")), key=lambda i: -(i.get("width") or 0))
    faixa = (ev.get("priceRanges") or [{}])[0]
    ender = ", ".join(x for x in ((v.get("address") or {}).get("line1"), (v.get("city") or {}).get("name")) if x)
    return {
        "fonte": "ticketmaster", "fonte_id": ev["id"], "titulo": ev["name"],
        "descricao": ev.get("info") or ev.get("pleaseNote") or "", "inicio": _data(ev.get("dates") or {}),
        "local_nome": v.get("name", ""), "endereco": ender,
        "lat": float(loc["latitude"]) if loc.get("latitude") else None, "lon": float(loc["longitude"]) if loc.get("longitude") else None,
        "url": ev.get("url", ""), "ingresso_url": ev.get("url", ""), "categoria": cat,
        "imagem_url": imgs[0]["url"] if imgs else "", "preco_min": faixa.get("min"), "gratuito": faixa.get("max") == 0,
    }


def coletar(chave: str | None = None, client=None, raio_km=40, max_paginas=5, pausa=0.3):
    chave = chave or os.getenv("TICKETMASTER_API_KEY")
    if not chave:
        print("ticketmaster: sem TICKETMASTER_API_KEY, ignorado")
        return []
    client = client or httpx.Client(timeout=30)
    saida, pagina = {}, 0
    while pagina < max_paginas:
        r = client.get(API, params={"apikey": chave, "latlong": CENTRO_SP, "radius": raio_km, "unit": "km", "countryCode": "BR",
                                    "size": 200, "page": pagina, "sort": "date,asc"})
        r.raise_for_status()
        j = r.json()
        for ev in (j.get("_embedded") or {}).get("events", []):
            n = normalizar(ev)
            if n:
                saida[n["fonte_id"]] = n
        if pagina + 1 >= (j.get("page") or {}).get("totalPages", 1):
            break
        pagina += 1
        time.sleep(pausa)
    return list(saida.values())
