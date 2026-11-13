"""Raspagem de sites específicos via JSON-LD (schema.org) - Event, Restaurant, BarOrPub.

Respeita robots.txt. Configure as URLs em sources.yml. Sympla e similares publicam
JSON-LD nas páginas de evento, então basta listar a URL; confira os termos de uso do site.
"""
import hashlib
import json
import re
import time
import urllib.robotparser
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
import httpx
import yaml
from bs4 import BeautifulSoup

UA = "guia-sp-api/1.0"
TIPOS_LUGAR = {"Restaurant": "restaurante", "FoodEstablishment": "restaurante", "CafeOrCoffeeShop": "restaurante",
               "FastFoodRestaurant": "restaurante", "BarOrPub": "bar", "NightClub": "bar"}


def robots_detalhe(url, client):
    """-> (resultado, motivo). resultado: 'ok' | 'proibido' | 'erro'. Segue o RFC 9309:
    robots.txt 4xx = sem restrições; 5xx ou sem resposta = não visitar (motivo diz qual)."""
    p = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = client.get(f"{p.scheme}://{p.netloc}/robots.txt")
    except httpx.HTTPError as exc:
        return "erro", type(exc).__name__
    if r.status_code >= 500:
        return "erro", f"HTTP {r.status_code}"
    rp.parse(r.text.splitlines() if r.status_code == 200 else [])
    return ("ok", "") if rp.can_fetch(UA, url) else ("proibido", "robots.txt")


def robots(url, client) -> str:
    return robots_detalhe(url, client)[0]


def permitido(url, client) -> bool:
    return robots(url, client) == "ok"


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


def _norm(t: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def da_cidade(ev: dict, cidade: str) -> bool:
    """Evento na cidade pedida? Usa o texto do endereço (que traz a localidade) ou, sem ele, as coordenadas."""
    if not cidade:
        return True
    if ev.get("endereco"):
        return _norm(cidade) in _norm(ev["endereco"])
    if ev.get("lat") is not None and ev.get("lon") is not None:
        return -24.01 <= ev["lat"] <= -23.35 and -46.83 <= ev["lon"] <= -46.36 if _norm(cidade) == "sao paulo" else False
    return False


def obter(client, url, tentativas=2):
    """GET que respeita 429/503: espera o Retry-After (até 30 s) e tenta de novo uma vez."""
    for i in range(tentativas):
        r = client.get(url)
        if r.status_code in (429, 503) and i + 1 < tentativas:
            try:
                espera = min(30, int(r.headers.get("retry-after", "10")))
            except ValueError:
                espera = 10
            time.sleep(espera)
            continue
        return r
    return r


def links_listagem(html: str, base_url: str, padrao: str, limite: int = 30) -> list[str]:
    """Links (mesmo site) de uma página de listagem que casam com `padrao` (regex no caminho). Sem duplicados."""
    rx = re.compile(padrao)
    host = urlparse(base_url).netloc.lower().removeprefix("www.")
    vistos, saida = set(), []
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        pu = urlparse(urljoin(base_url, a["href"].strip()))
        q = [(k, v) for k, v in parse_qsl(pu.query) if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid", "ref")]
        u = urlunparse(pu._replace(query=urlencode(q), fragment=""))  # tira rastreamento, mantém ?id=123
        if pu.scheme in ("http", "https") and pu.netloc.lower().removeprefix("www.") == host and rx.search(pu.path) and u not in vistos:
            vistos.add(u)
            saida.append(u)
            if len(saida) >= limite:
                break
    return saida


def coletar(config_path="sources.yml", client=None, pausa=1.0):
    client = client or httpx.Client(timeout=30, headers={"User-Agent": UA}, follow_redirects=True)
    cfg = yaml.safe_load(open(config_path, encoding="utf-8")) or {}
    lugares, eventos, ignorados = [], [], []
    for s in cfg.get("sites") or []:
        if s.get("ativo", True) is False:
            continue
        url, cidade, esp = s["url"], s.get("cidade", ""), float(s.get("pausa", pausa))
        if not permitido(url, client):
            ignorados.append(url)
            continue
        r = obter(client, url)
        r.raise_for_status()
        l, e = extrair(r.text, url, s.get("tipo", "evento"))
        lugares += l
        eventos += [x for x in e if da_cidade(x, cidade)]
        if s.get("listagem"):  # a lista não tem JSON-LD: segue os links das páginas de cada evento
            for u in links_listagem(r.text, str(r.url), s["padrao_link"], int(s.get("limite", 30))):
                if not permitido(u, client):
                    ignorados.append(u)
                    continue
                try:
                    rd = obter(client, u)
                    rd.raise_for_status()
                except httpx.HTTPError:
                    continue
                l, e = extrair(rd.text, u, s.get("tipo", "evento"))
                lugares += l
                eventos += [x for x in e if da_cidade(x, cidade)]
                time.sleep(esp)
    return lugares, eventos, ignorados
