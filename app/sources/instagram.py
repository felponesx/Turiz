"""Vínculo Instagram <-> restaurante/bar SEM raspar o Instagram (viola os termos e é bloqueado).

Origens do vínculo:
  osm_tag     - tag contact:instagram cadastrada no OpenStreetMap para o lugar (confiança 0.90)
  site        - link para o Instagram publicado no site oficial do lugar (confiança 0.70)
  api_oficial - verificação via Instagram Graph API (Business Discovery) quando há credenciais:
                compara nome do perfil e site com os do lugar e eleva para "confirmado" (0.98).
Business Discovery só enxerga contas profissionais (comerciais/criador) e exige INSTAGRAM_TOKEN +
INSTAGRAM_USER_ID de uma conta profissional sua ligada a uma página do Facebook.
Não existe busca por nome na API oficial: sem handle de OSM/site, não há vínculo automático.
"""
import re
import time
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from .sites import permitido, UA

RESERVADOS = {"p", "reel", "reels", "explore", "accounts", "stories", "tv", "share", "direct", "about", "legal",
              "developer", "web", "challenge", "directory", "locations", "oauth", "privacy", "terms", "instagram"}
PADRAO = re.compile(r"(?:https?:)?(?://)?(?:www\.)?instagram\.com/([A-Za-z0-9._]{1,30})(?=[/?#\"'\s]|$)", re.I)
GRAPH = "https://graph.facebook.com/v21.0"


def normalizar_usuario(valor: str) -> str | None:
    v = (valor or "").strip()
    m = PADRAO.search(v)
    u = m.group(1) if m else v.lstrip("@").strip("/ ")
    u = u.lower()
    if not re.fullmatch(r"[a-z0-9._]{1,30}", u) or u in RESERVADOS:
        return None
    return u


def usuarios_do_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    achados = []
    for a in soup.find_all("a", href=True):
        u = normalizar_usuario(a["href"]) if "instagram.com" in a["href"].lower() else None
        if u and u not in achados:
            achados.append(u)
    return achados


def _limpa(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


def similaridade(a: str, b: str) -> float:
    a, b = _limpa(a), _limpa(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.9
    return SequenceMatcher(None, a, b).ratio()


def _dominio(url: str) -> str:
    h = urlparse(url if "//" in url else "//" + url).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def verificar(usuario: str, nome_lugar: str, site_lugar: str, token: str, ig_user_id: str, client) -> dict | None:
    """Consulta Business Discovery. Retorna dados do perfil + 'confere' (bool), ou None se não for conta profissional."""
    campos = "business_discovery.username(%s){username,name,biography,website,followers_count,media_count}" % usuario
    r = client.get(f"{GRAPH}/{ig_user_id}", params={"fields": campos, "access_token": token})
    if r.status_code in (400, 404):
        return None  # conta pessoal, inexistente ou sem permissão
    r.raise_for_status()
    bd = r.json().get("business_discovery")
    if not bd:
        return None
    sim = max(similaridade(nome_lugar, bd.get("name", "")), similaridade(nome_lugar, bd.get("username", "")))
    dom = bool(site_lugar and bd.get("website") and _dominio(site_lugar) == _dominio(bd["website"]))
    return {"nome_perfil": bd.get("name", ""), "seguidores": bd.get("followers_count"), "similaridade": round(sim, 2),
            "site_confere": dom, "confere": sim >= 0.6 or dom, "bio": (bd.get("biography") or "")[:300]}


def vinculos_osm(lugar: dict) -> list[dict]:
    u = normalizar_usuario((lugar.get("extra") or {}).get("contact:instagram", ""))
    return [_reg(lugar, u, "osm_tag", 0.90, "confirmado")] if u else []


def _reg(lugar, usuario, origem, conf, status):
    return {"lugar_fonte": lugar["fonte"], "lugar_fonte_id": lugar["fonte_id"], "rede": "instagram", "usuario": usuario,
            "url": f"https://www.instagram.com/{usuario}/", "origem": origem, "confianca": conf, "status": status}


def vinculos_sites(lugares: list[dict], client=None, pausa=1.0, limite=None):
    client = client or httpx.Client(timeout=20, headers={"User-Agent": UA}, follow_redirects=True)
    saida, bloqueados, falhas = [], 0, 0
    for l in lugares[:limite]:
        url = l["site"] if l["site"].startswith("http") else "https://" + l["site"]
        try:
            if not permitido(url, client):
                bloqueados += 1
                continue
            r = client.get(url)
            r.raise_for_status()
        except httpx.HTTPError:
            falhas += 1
            continue
        for u in usuarios_do_html(r.text)[:3]:
            saida.append(_reg(l, u, "site", 0.70, "provavel"))
        time.sleep(pausa)
    return saida, {"bloqueados_robots": bloqueados, "falhas": falhas}
