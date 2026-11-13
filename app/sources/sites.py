"""Raspagem de sites específicos via JSON-LD (schema.org) - Event, Restaurant, BarOrPub.

Respeita robots.txt. Configure as URLs em sources.yml. Sympla e similares publicam
JSON-LD nas páginas de evento, então basta listar a URL; confira os termos de uso do site.
"""
import hashlib
import json
import urllib.robotparser
from datetime import datetime
from urllib.parse import urlparse
import httpx
import yaml
from bs4 import BeautifulSoup

UA = "guia-sp-api/1.0"
TIPOS_LUGAR = {"Restaurant": "restaurante", "FoodEstablishment": "restaurante", "CafeOrCoffeeShop": "restaurante",
               "FastFoodRestaurant": "restaurante", "BarOrPub": "bar", "NightClub": "bar"}


def permitido(url, client) -> bool:
    p = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = client.get(f"{p.scheme}://{p.netloc}/robots.txt")
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
    except httpx.HTTPError:
        return False
    return rp.can_fetch(UA, url)


def itens_jsonld(html: str):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            dado = json.loads(tag.string or "")
        except ValueError:
            continue
        fila = dado if isinstance(dado, list) else [dado]
        while fila:
            x = fila.pop()
            if isinstance(x, dict):
                if "@graph" in x:
                    fila += x["@graph"]
                yield x


def _data(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None
    except ValueError:
        return None


def _endereco(a):
    if isinstance(a, str):
        return a
    if isinstance(a, dict):
        return ", ".join(str(a[k]) for k in ("streetAddress", "addressLocality") if a.get(k))
    return ""


CATEGORIAS = {"MusicEvent": "musica", "TheaterEvent": "teatro", "ComedyEvent": "comedia", "FoodEvent": "gastronomia",
              "Festival": "festival", "DanceEvent": "danca", "ExhibitionEvent": "exposicao", "SportsEvent": "esporte",
              "ScreeningEvent": "cinema", "EducationEvent": "curso", "SocialEvent": "festa", "BusinessEvent": "negocios"}


def _categoria(tipos):
    return next((CATEGORIAS[t] for t in tipos if t in CATEGORIAS), "evento")


def _imagem(i):
    i = i[0] if isinstance(i, list) and i else i
    if isinstance(i, dict):
        i = i.get("url")
    return i if isinstance(i, str) and i.startswith("http") else ""


def _oferta(o, url_padrao):
    """schema.org Offer(s) -> preço mínimo, gratuito e link de ingresso."""
    ofs = [x for x in (o if isinstance(o, list) else [o]) if isinstance(x, dict)]
    precos = []
    for x in ofs:
        for k in ("price", "lowPrice"):
            try:
                precos.append(float(str(x[k]).replace(",", ".")))
            except (KeyError, ValueError):
                pass
    link = next((x["url"] for x in ofs if isinstance(x.get("url"), str) and x["url"].startswith("http")), "")
    return {"preco_min": min(precos) if precos else None, "gratuito": bool(precos) and min(precos) == 0, "ingresso_url": link or ""}


def _id(url, nome):
    return hashlib.sha1(f"{url}|{nome}".encode()).hexdigest()[:20]


def extrair(html: str, url: str, tipo_padrao: str):
    """Retorna (lugares, eventos) normalizados."""
    lugares, eventos = [], []
    for x in itens_jsonld(html):
        tipos = x.get("@type")
        tipos = tipos if isinstance(tipos, list) else [tipos]
        nome = x.get("name", "")
        if "Event" in tipos or any(isinstance(t, str) and t.endswith("Event") for t in tipos):
            loc = x.get("location") or {}
            loc = loc[0] if isinstance(loc, list) and loc else loc
            geo = (loc.get("geo") or {}) if isinstance(loc, dict) else {}
            eventos.append({
                "fonte": "site", "fonte_id": _id(x.get("url") or url, nome), "titulo": nome,
                "descricao": x.get("description", ""), "inicio": _data(x.get("startDate")),
                "fim": _data(x.get("endDate")),
                "local_nome": loc.get("name", "") if isinstance(loc, dict) else "",
                "endereco": _endereco(loc.get("address") if isinstance(loc, dict) else ""),
                "lat": float(geo["latitude"]) if geo.get("latitude") else None,
                "lon": float(geo["longitude"]) if geo.get("longitude") else None,
                "url": x.get("url") or url,
                "categoria": _categoria(tipos), "imagem_url": _imagem(x.get("image")),
                **_oferta(x.get("offers"), x.get("url") or url),
            })
        else:
            tipo = next((TIPOS_LUGAR[t] for t in tipos if t in TIPOS_LUGAR), None)
            if tipo and nome:
                geo = x.get("geo") or {}
                lugares.append({
                    "fonte": "site", "fonte_id": _id(x.get("url") or url, nome), "tipo": tipo, "nome": nome,
                    "culinaria": str(x.get("servesCuisine", "")), "endereco": _endereco(x.get("address")),
                    "lat": float(geo["latitude"]) if geo.get("latitude") else None,
                    "lon": float(geo["longitude"]) if geo.get("longitude") else None,
                    "telefone": x.get("telephone", ""), "site": x.get("url") or url,
                })
    return lugares, eventos


def coletar(config_path="sources.yml", client=None):
    client = client or httpx.Client(timeout=30, headers={"User-Agent": UA}, follow_redirects=True)
    cfg = yaml.safe_load(open(config_path, encoding="utf-8")) or {}
    lugares, eventos, ignorados = [], [], []
    for s in cfg.get("sites") or []:
        url = s["url"]
        if not permitido(url, client):
            ignorados.append(url)
            continue
        r = client.get(url)
        r.raise_for_status()
        l, e = extrair(r.text, url, s.get("tipo", "evento"))
        lugares += l
        eventos += e
    return lugares, eventos, ignorados
