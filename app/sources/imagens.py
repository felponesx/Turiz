"""Bot de imagens: reúne REFERÊNCIAS (url, autor, licença) de fotos de restaurantes e bares.

Fontes, da mais segura para a menos:
  commons  - Wikimedia Commons, via tags `wikimedia_commons` / `wikidata` (P18) do OSM.
             Licença e autor vêm da própria API -> status "aprovada" se a licença for livre.
  osm_image- tag `image` do OSM apontando para outro site: licença desconhecida -> "pendente".
  site     - og:image do site oficial do estabelecimento (respeita robots.txt):
             direitos do dono -> sempre "pendente" até alguém aprovar/ter permissão.

Não baixamos nem republicamos os arquivos; só guardamos a referência e os créditos.
"""
import re
import time
from urllib.parse import quote, unquote, urlparse
import httpx
from bs4 import BeautifulSoup
from . import osm
from .sites import permitido, UA, cliente_http

# A Wikimedia exige User-Agent descritivo com contato (aqui, o repositório).
UA_WIKI = "TurizImagensBot/1.0 (https://github.com/felponesx/Turiz; image reference bot)"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
# Licenças consideradas livres para uso com atribuição (confira a lista antes de publicar).
LIVRES = re.compile(r"^(CC0|Public domain|PD|CC BY(-SA)?( [\d.]+)?|CC BY(-SA)? [\d.]+ [A-Za-z]+|GFDL)", re.I)
TIPOS = "restaurant|fast_food|cafe|bar|pub|food_court|biergarten"


def query_tags():
    s, w, n, e = osm.BBOX_SP
    filtros = "".join(f'nwr(area.sp)({s},{w},{n},{e})["amenity"~"^({TIPOS})$"]["name"]{f};\n' for f in ('["wikimedia_commons"]', '["wikidata"]', '["image"]'))
    return ('[out:json][timeout:180];\narea["name"="São Paulo"]["boundary"="administrative"]["admin_level"="8"]->.sp;\n(\n' + filtros + ');\nout tags;')


def _titulo_commons(valor: str) -> str | None:
    v = unquote(valor.strip())
    m = re.search(r"commons\.wikimedia\.org/wiki/(File:.+)$", v) or re.search(r"^(File:.+)$", v, re.I)
    return m.group(1).replace("_", " ") if m else None


def _limpa(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)


def info_commons(titulos: list[str], client) -> dict[str, dict]:
    """Resolve até 50 títulos 'File:...' em {titulo: info} (url, thumb, licença, autor)."""
    saida = {}
    for i in range(0, len(titulos), 50):
        lote = titulos[i:i + 50]
        try:
            r = client.get(COMMONS_API, params={"action": "query", "format": "json", "titles": "|".join(lote), "prop": "imageinfo",
                                                "iiprop": "url|size|extmetadata", "iiurlwidth": 800})
            r.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"  aviso: lote do Commons falhou: {exc}")
            continue
        for pg in r.json().get("query", {}).get("pages", {}).values():
            ii = (pg.get("imageinfo") or [None])[0]
            if not ii:
                continue
            md = ii.get("extmetadata", {})
            lic = md.get("LicenseShortName", {}).get("value", "")
            saida[pg["title"]] = {
                "url": ii["url"], "thumb_url": ii.get("thumburl", ""), "largura": ii.get("width"), "altura": ii.get("height"),
                "licenca": lic, "autor": _limpa(md.get("Artist", {}).get("value", "")), "creditos_url": ii.get("descriptionurl", ""),
                "status": "aprovada" if LIVRES.match(lic) else "pendente",
            }
        time.sleep(1)
    return saida


def p18_wikidata(qids: list[str], client) -> dict[str, str]:
    """{Qid: 'File:nome.jpg'} usando a propriedade P18 (imagem)."""
    saida = {}
    for i in range(0, len(qids), 50):
        try:
            r = client.get(WIKIDATA_API, params={"action": "wbgetentities", "format": "json", "props": "claims", "ids": "|".join(qids[i:i + 50])})
            r.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"  aviso: lote da Wikidata falhou: {exc}")
            continue
        for q, ent in r.json().get("entities", {}).items():
            for c in ent.get("claims", {}).get("P18", [])[:1]:
                v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
                if v:
                    saida[q] = "File:" + v
        time.sleep(1)
    return saida


def coletar_commons(post=None, client=None):
    """Retorna lista de imagens normalizadas ligadas aos lugares do OSM."""
    post = post or osm._post
    client = client or httpx.Client(timeout=60, headers={"User-Agent": UA_WIKI})
    elementos = post(query_tags()).get("elements", [])
    pedidos = []  # (lugar_fonte_id, titulo_ou_qid, origem)
    qids = {}
    for el in elementos:
        t = el.get("tags", {})
        fid = f'{el["type"]}/{el["id"]}'
        if t.get("wikimedia_commons"):
            tit = _titulo_commons(t["wikimedia_commons"])
            if tit:
                pedidos.append((fid, tit))
        if t.get("wikidata", "").startswith("Q"):
            qids[fid] = t["wikidata"]
        if t.get("image") and _titulo_commons(t["image"]):
            pedidos.append((fid, _titulo_commons(t["image"])))
    p18 = p18_wikidata(sorted(set(qids.values())), client) if qids else {}
    for fid, q in qids.items():
        if q in p18:
            pedidos.append((fid, p18[q]))
    infos = info_commons(sorted({t for _, t in pedidos}), client)
    print(f"  commons: {len(elementos)} lugares com tag de imagem | {len(qids)} com wikidata | "
          f"{len(p18)} com P18 | {len(pedidos)} arquivos pedidos | {len(infos)} resolvidos")
    saida, vistos = [], set()
    for fid, tit in pedidos:
        i = infos.get(tit)
        if i and (fid, i["url"]) not in vistos:
            vistos.add((fid, i["url"]))
            saida.append({"lugar_fonte": "osm", "lugar_fonte_id": fid, "fonte": "commons", **i})
    # tag image com URL que não é do Commons: referência sem licença conhecida
    for el in elementos:
        u = el.get("tags", {}).get("image", "")
        if u.startswith("http") and not _titulo_commons(u):
            saida.append({"lugar_fonte": "osm", "lugar_fonte_id": f'{el["type"]}/{el["id"]}', "fonte": "osm_image", "url": u,
                          "thumb_url": "", "licenca": "", "autor": "", "creditos_url": "", "status": "pendente"})
    return saida


def og_image(html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for attrs in ({"property": "og:image"}, {"name": "twitter:image"}, {"property": "og:image:url"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            c = tag["content"].strip()
            if c.startswith("//"):
                c = "https:" + c
            elif c.startswith("/"):
                p = urlparse(base_url)
                c = f"{p.scheme}://{p.netloc}{c}"
            return c if c.startswith("http") else None
    return None


def coletar_sites(lugares: list[dict], client=None, pausa=1.0, limite=None):
    """lugares: [{'fonte','fonte_id','site'}]. Pega o og:image do site oficial (status pendente)."""
    client = client or cliente_http(20)
    saida, bloqueados, falhas = [], 0, 0
    for l in lugares[:limite]:
        url = l["site"] if l["site"].startswith("http") else "https://" + l["site"]
        try:
            if not permitido(url, client):
                bloqueados += 1
                continue
            r = client.get(url)
            r.raise_for_status()
            img = og_image(r.text, str(r.url))
        except httpx.HTTPError:
            falhas += 1
            continue
        if img:
            saida.append({"lugar_fonte": l["fonte"], "lugar_fonte_id": l["fonte_id"], "fonte": "site", "url": img, "thumb_url": "",
                          "licenca": "direitos do estabelecimento", "autor": "", "creditos_url": url, "status": "pendente"})
        time.sleep(pausa)
    return saida, {"bloqueados_robots": bloqueados, "falhas": falhas}
