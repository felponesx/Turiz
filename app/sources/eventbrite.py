"""Eventbrite: lista eventos das organizações/locais que você controla.

A busca pública de eventos da Eventbrite foi descontinuada; a API v3 só lista eventos
de uma organização (ORG_ID) ou de um local (venue) acessível pelo seu token.
Defina EVENTBRITE_TOKEN e passe os org_ids.
"""
import os
from datetime import datetime
import httpx

BASE = "https://www.eventbriteapi.com/v3"


def _dt(d):
    return datetime.fromisoformat(d["utc"].replace("Z", "+00:00")) if d else None


def normalizar(e: dict) -> dict:
    v = e.get("venue") or {}
    a = v.get("address") or {}
    return {
        "fonte": "eventbrite", "fonte_id": e["id"],
        "titulo": (e.get("name") or {}).get("text", ""),
        "descricao": (e.get("description") or {}).get("text") or "",
        "inicio": _dt(e.get("start")), "fim": _dt(e.get("end")),
        "local_nome": v.get("name", ""), "endereco": a.get("localized_address_display", ""),
        "lat": float(v["latitude"]) if v.get("latitude") else None,
        "lon": float(v["longitude"]) if v.get("longitude") else None,
        "url": e.get("url", ""),
    }


def coletar(org_ids, token=None, client=None):
    token = token or os.getenv("EVENTBRITE_TOKEN")
    if not token:
        raise RuntimeError("Defina EVENTBRITE_TOKEN")
    client = client or httpx.Client(timeout=30)
    saida = []
    for org in org_ids:
        pagina = 1
        while True:
            r = client.get(f"{BASE}/organizations/{org}/events/", params={"expand": "venue", "status": "live", "page": pagina},
                           headers={"Authorization": f"Bearer {token}"})
            r.raise_for_status()
            d = r.json()
            saida += [normalizar(e) for e in d.get("events", [])]
            if not d.get("pagination", {}).get("has_more_items"):
                break
            pagina += 1
    return saida
