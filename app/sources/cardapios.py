"""Bot de cardápios: acha o cardápio OFICIAL de cada lugar a partir do site do próprio estabelecimento.

O que guardamos (nunca o arquivo):
  jsonld    - o site publica o cardápio em schema.org (Menu/MenuSection/MenuItem): itens e preços, status "confirmado".
  osm_tag   - tag `website:menu` / `menu:url` do OpenStreetMap, status "confirmado".
  link_site - link "Cardápio"/"Menu" na página inicial (próprio site, plataforma de cardápio, PDF ou imagem), status "provavel".

Respeita robots.txt, visita só a página inicial de cada site e não segue Instagram/Facebook (bloqueiam bots e
os termos proíbem raspagem). Plataformas de delivery (iFood etc.) entram só como LINK; não lemos o conteúdo delas.
"""
import re
import time
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from collections import Counter
from .sites import cliente_http, itens_jsonld, robots_detalhe

PLATAFORMAS = {
    "goomer": ("goomer.app", "goomer.com.br"), "menudino": ("menudino.com",), "anotaai": ("anota.ai",),
    "cardapioweb": ("cardapioweb.com",), "ifood": ("ifood.com.br",),
    "outro": ("neemo.com.br", "deliverydireto.com.br", "saipos.com", "wabiz.delivery", "cardapio.menu", "qrmenu", "pedidosnow"),
}
REDES = ("instagram.com", "facebook.com", "fb.com", "tiktok.com", "twitter.com", "x.com", "wa.me", "whatsapp.com", "linktr.ee")
_PALAVRA = re.compile(r"card[aá]pio|\bmenu\b|carta\s+de\s+(vinhos|bebidas|drinks)", re.I)
_CAMINHO = re.compile(r"/(card[aá]pio|menu|carta|cardapios)(/|\.|$|-)", re.I)


def _host(url: str) -> str:
    return (urlparse(url).netloc or "").lower().removeprefix("www.")


def _plataforma(url: str) -> str | None:
    h = _host(url)
    for nome, dominios in PLATAFORMAS.items():
        if any(h == d or h.endswith("." + d) or d in h for d in dominios):
            return nome
    return None


def _preco(o):
    if isinstance(o, list):
        o = o[0] if o else {}
    if isinstance(o, dict) and o.get("price") not in (None, ""):
        try:
            return float(str(o["price"]).replace(",", "."))
        except ValueError:
            return None
    return None


def itens_do_jsonld(html: str):
    """-> (url_do_menu, [itens]) a partir de Menu/hasMenu em schema.org. ('', []) se não houver."""
    url, itens = "", []
    for x in itens_jsonld(html):
        tipos = x.get("@type")
        tipos = tipos if isinstance(tipos, list) else [tipos]
        menu = x if "Menu" in tipos else None
        hm = x.get("hasMenu")
        if isinstance(hm, str):
            url = url or hm
        elif isinstance(hm, dict):
            menu = menu or hm
        elif isinstance(hm, list):
            menu = menu or next((m for m in hm if isinstance(m, dict)), None)
            url = url or next((m for m in hm if isinstance(m, str)), "")
        if not isinstance(menu, dict):
            continue
        url = url or str(menu.get("url") or "")
        secoes = menu.get("hasMenuSection") or []
        for sec in secoes if isinstance(secoes, list) else [secoes]:
            if not isinstance(sec, dict):
                continue
            its = sec.get("hasMenuItem") or []
            for it in its if isinstance(its, list) else [its]:
                if isinstance(it, dict) and it.get("name"):
                    itens.append({"secao": str(sec.get("name", "")), "nome": str(it["name"]), "descricao": str(it.get("description", "")),
                                  "preco": _preco(it.get("offers"))})
    return url, itens[:300]


def buscar(html: str, base_url: str, menu_osm: str = "") -> list[dict]:
    """Pura (sem rede): devolve até 3 cardápios candidatos de uma página inicial."""
    achados, vistos = [], set()

    def add(url, origem, status, itens=None):
        if not url or url in vistos or not url.startswith("http"):
            return
        vistos.add(url)
        u = urlparse(url).path.lower()
        plat = _plataforma(url) or ("pdf" if u.endswith(".pdf") else "imagem" if re.search(r"\.(jpe?g|png|webp)$", u) else
                                    "proprio" if _host(url) == _host(base_url) else "outro")
        achados.append({"url": url, "plataforma": plat, "origem": origem, "itens": itens or [], "status": status})

    if menu_osm:
        status = "confirmado"
        add(menu_osm, "osm_tag", status)
    url_ld, itens = itens_do_jsonld(html)
    if url_ld or itens:
        status = "confirmado"
        add(urljoin(base_url, url_ld) if url_ld else base_url, "jsonld", status, itens)
    status = "provavel"
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        url = urljoin(base_url, href)
        h = _host(url)
        if not h or any(h == r or h.endswith("." + r) for r in REDES):
            continue
        texto = a.get_text(" ", strip=True)
        plat = _plataforma(url)
        eh_arquivo = bool(re.search(r"\.(pdf|jpe?g|png|webp)(\?|$)", url, re.I))
        relevante = bool(_PALAVRA.search(texto) or _PALAVRA.search(urlparse(url).path))
        if plat or (eh_arquivo and relevante) or (_CAMINHO.search(urlparse(url).path) and h == _host(base_url)) or \
                (relevante and h != _host(base_url) and len(texto) < 40 and _PALAVRA.search(texto)):
            add(url, "link_site", status)
        if len(achados) >= 3:
            break
    return achados[:3]


def coletar(lugares: list[dict], client=None, pausa=1.0, limite=None):
    """lugares: [{'fonte','fonte_id','site','menu_osm'}]. Retorna (registros, stats)."""
    client = client or cliente_http(20)
    saida, st = [], {"visitados": 0, "bloqueados_robots": 0, "robots_sem_resposta": 0, "motivos_sem_resposta": Counter(), "falhas": 0, "ignorados_rede_social": 0, "com_cardapio": 0}
    for l in lugares[:limite]:
        site = (l.get("site") or "").strip()
        osm_menu = (l.get("menu_osm") or "").strip()
        achados = []
        if site:
            url = site if site.startswith("http") else "https://" + site
            if any(_host(url) == r or _host(url).endswith("." + r) for r in REDES):
                st["ignorados_rede_social"] += 1
            else:
                try:
                    rb, motivo = robots_detalhe(url, client)
                    if rb != "ok":
                        st["bloqueados_robots" if rb == "proibido" else "robots_sem_resposta"] += 1
                        if rb == "erro":
                            st["motivos_sem_resposta"][motivo] += 1
                    else:
                        r = client.get(url)
                        r.raise_for_status()
                        st["visitados"] += 1
                        achados = buscar(r.text, str(r.url), osm_menu)
                except httpx.HTTPError:
                    st["falhas"] += 1
                time.sleep(pausa)
        elif osm_menu:
            achados = buscar("", osm_menu, osm_menu)
        if achados:
            st["com_cardapio"] += 1
        for a in achados:
            saida.append({"lugar_fonte": l["fonte"], "lugar_fonte_id": l["fonte_id"], **a})
    return saida, st
