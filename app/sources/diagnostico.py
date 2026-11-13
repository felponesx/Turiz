"""Diagnóstico de fontes: testa se cada fonte candidata responde para um robô e que dados estruturados ela expõe.

Para cada URL: status HTTP, bloqueio (captcha/Cloudflare), robots.txt, JSON-LD (eventos e lugares) e, quando é
API, se "precisa de chave" (401/403 sem chave é o esperado). Não coleta nada: só mede e gera relatório.
"""
import json
import re
import time
import httpx
from urllib.parse import urljoin, urlparse
from .sites import cliente_http, itens_jsonld, permitido

# categoria: evento | lugar | cardapio | avaliacao | dados_abertos | imagem. tipo: html | api | arquivo.
FONTES = [
    # --- infraestrutura que os bots já usam
    {"id": "overpass", "categoria": "lugar", "tipo": "api", "url": "https://overpass-api.de/api/status", "nota": "restaurantes e bares do OSM"},
    {"id": "nominatim", "categoria": "lugar", "tipo": "api", "url": "https://nominatim.openstreetmap.org/status.php?format=json", "nota": "endereços (1 req/s)"},
    {"id": "commons", "categoria": "imagem", "tipo": "api", "url": "https://commons.wikimedia.org/w/api.php?action=query&meta=siteinfo&format=json", "nota": "fotos com licença livre"},
    {"id": "wikidata", "categoria": "lugar", "tipo": "api", "url": "https://query.wikidata.org/sparql?query=SELECT%20%3Fs%20WHERE%20%7B%3Fs%20%3Fp%20%3Fo%7D%20LIMIT%201&format=json", "nota": "ligações com wikidata/P18"},
    # --- dados abertos oficiais
    {"id": "cnpj_receita", "categoria": "dados_abertos", "tipo": "arquivo", "url": "https://dadosabertos.rfb.gov.br/CNPJ/", "nota": "estabelecimentos CNAE 5611 (restaurantes/bares): ampliaria a base"},
    {"id": "cnpj_receita_novo", "categoria": "dados_abertos", "tipo": "arquivo", "url": "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/", "nota": "novo endereço dos mesmos dados"},
    {"id": "cnpj_brasilapi", "categoria": "dados_abertos", "tipo": "api", "url": "https://brasilapi.com.br/api/cnpj/v1/00000000000191", "nota": "consulta de um CNPJ por vez"},
    {"id": "brasilapi_cep", "categoria": "dados_abertos", "tipo": "api", "url": "https://brasilapi.com.br/api/cep/v2/01001000", "nota": "CEP -> coordenadas"},
    {"id": "sp_dados_abertos", "categoria": "dados_abertos", "tipo": "api", "url": "https://dados.prefeitura.sp.gov.br/api/3/action/package_list", "nota": "CKAN da Prefeitura de SP"},
    {"id": "geofabrik_sp", "categoria": "lugar", "tipo": "arquivo", "url": "https://download.geofabrik.de/south-america/brazil/sudeste.html", "nota": "extrato OSM completo (alternativa ao Overpass)"},
    # --- eventos: instituições públicas e culturais
    {"id": "sescsp", "categoria": "evento", "tipo": "html", "url": "https://www.sescsp.org.br/programacao/", "nota": "programação do Sesc SP"},
    {"id": "prefeitura_agenda", "categoria": "evento", "tipo": "html", "url": "https://www.prefeitura.sp.gov.br/cidade/secretarias/cultura/", "nota": "Secretaria Municipal de Cultura"},
    {"id": "theatro_municipal", "categoria": "evento", "tipo": "html", "url": "https://theatromunicipal.org.br/", "nota": "Theatro Municipal"},
    {"id": "visite_sp", "categoria": "evento", "tipo": "html", "url": "https://www.visitesaopaulo.com/", "nota": "SPTuris, agenda da cidade"},
    # --- eventos: plataformas de ingresso e guias
    {"id": "sympla", "categoria": "evento", "tipo": "html", "url": "https://www.sympla.com.br/eventos/sao-paulo-sp", "nota": "sem API pública de busca"},
    {"id": "eventbrite", "categoria": "evento", "tipo": "html", "url": "https://www.eventbrite.com.br/d/brazil--s%C3%A3o-paulo/events/", "nota": "sem busca pública pela API"},
    {"id": "ingresso_com", "categoria": "evento", "tipo": "html", "url": "https://www.ingresso.com/", "nota": "cinema/teatro"},
    {"id": "ticketmaster_api", "categoria": "evento", "tipo": "api", "url": "https://app.ticketmaster.com/discovery/v2/events.json?countryCode=BR&size=1", "nota": "API oficial (chave gratuita)"},
    {"id": "ticket360", "categoria": "evento", "tipo": "html", "url": "https://www.ticket360.com.br/", "nota": "shows e festas"},
    {"id": "bilheteria_digital", "categoria": "evento", "tipo": "html", "url": "https://www.bilheteriadigital.com/", "nota": "shows e festas"},
    {"id": "timeout_sp", "categoria": "evento", "tipo": "html", "url": "https://www.timeout.com/sao-paulo", "nota": "guia"},
    {"id": "guia_folha", "categoria": "evento", "tipo": "html", "url": "https://guia.folha.uol.com.br/", "nota": "guia"},
    {"id": "veja_sp", "categoria": "evento", "tipo": "html", "url": "https://vejasp.abril.com.br/", "nota": "guia"},
    {"id": "guia_da_semana", "categoria": "evento", "tipo": "html", "url": "https://www.guiadasemana.com.br/sao-paulo", "nota": "guia"},
    {"id": "bandsintown_api", "categoria": "evento", "tipo": "api", "url": "https://rest.bandsintown.com/artists/Coldplay?app_id=turiz", "nota": "exige app_id aprovado"},
    {"id": "meetup", "categoria": "evento", "tipo": "html", "url": "https://www.meetup.com/find/?location=br--S%C3%A3o+Paulo", "nota": "API só com OAuth"},
    # --- avaliações / lugares de terceiros (só para saber se há API oficial acessível; não guardamos notas de terceiros)
    {"id": "foursquare_api", "categoria": "avaliacao", "tipo": "api", "url": "https://places-api.foursquare.com/places/search?query=pizza&near=Sao%20Paulo", "nota": "API oficial, exige chave"},
    {"id": "tripadvisor_api", "categoria": "avaliacao", "tipo": "api", "url": "https://api.content.tripadvisor.com/api/v1/location/search?searchQuery=pizza", "nota": "API oficial, exige chave"},
    {"id": "google_places_api", "categoria": "avaliacao", "tipo": "api", "url": "https://places.googleapis.com/v1/places:searchText", "nota": "API oficial paga (coletor google já existe)"},
    {"id": "tomtom_api", "categoria": "lugar", "tipo": "api", "url": "https://api.tomtom.com/search/2/poiSearch/pizza.json?lat=-23.55&lon=-46.63", "nota": "POIs, exige chave"},
    # --- cardápios / delivery (só link; os termos proíbem raspar o conteúdo)
    {"id": "ifood", "categoria": "cardapio", "tipo": "html", "url": "https://www.ifood.com.br/restaurantes", "nota": "não raspamos: só guardamos o link informado pelo restaurante"},
    {"id": "goomer", "categoria": "cardapio", "tipo": "html", "url": "https://goomer.app/", "nota": "plataforma de cardápio digital"},
    {"id": "menudino", "categoria": "cardapio", "tipo": "html", "url": "https://www.menudino.com/", "nota": "plataforma de cardápio digital"},
    {"id": "anotaai", "categoria": "cardapio", "tipo": "html", "url": "https://anota.ai/", "nota": "plataforma de cardápio digital"},
]
_BLOQUEIO = re.compile(r"captcha|cf-chl|just a moment|attention required|access denied|px-captcha|cloudflare ray id|verifique que você é humano", re.I)


_DETALHE = re.compile(r"/(eventos?|events?|shows?|ingressos?|programacao|agenda|espetaculos?|festas?)/[^/?#]+", re.I)


def contar_jsonld(html: str):
    ev = lg = 0
    for x in itens_jsonld(html):
        t = x.get("@type")
        for tt in (t if isinstance(t, list) else [t]):
            if isinstance(tt, str) and tt.endswith("Event"):
                ev += 1
            elif tt in ("Restaurant", "BarOrPub", "FoodEstablishment", "CafeOrCoffeeShop", "NightClub"):
                lg += 1
    return ev, lg


def candidatos_detalhe(html: str, base_url: str, n: int = 5) -> list[str]:
    host = urlparse(base_url).netloc.lower().removeprefix("www.")
    vistos, saida = set(), []
    from bs4 import BeautifulSoup
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        u = urljoin(base_url, a["href"].strip()).split("#")[0].split("?")[0]
        pu = urlparse(u)
        if pu.netloc.lower().removeprefix("www.") == host and _DETALHE.search(pu.path) and pu.path.rstrip("/") != urlparse(base_url).path.rstrip("/") and u not in vistos:
            vistos.add(u)
            saida.append(u)
            if len(saida) >= n:
                break
    return saida


def _modelo(path: str) -> str:
    """'/evento/33890/ingressos-para-x' -> '/evento/*/*'. Mantém só o primeiro trecho do caminho."""
    partes = [p for p in path.split("/") if p]
    return "/" + "/".join(partes[:1] + ["*"] * len(partes[1:])) if partes else "/"


def descobrir_padroes(html: str, base_url: str, client, grupos: int = 8, amostra: int = 2, pausa: float = 1.0) -> list[dict]:
    """Agrupa os links do mesmo site pelo formato do caminho e testa amostras de cada grupo (JSON-LD Event).
    Devolve os grupos ordenados por acerto; `padrao_sugerido` é o regex para usar em `padrao_link`."""
    from bs4 import BeautifulSoup
    host = urlparse(base_url).netloc.lower().removeprefix("www.")
    por_grupo: dict[str, list[str]] = {}
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        u = urljoin(base_url, a["href"].strip()).split("#")[0]
        pu = urlparse(u)
        if pu.scheme in ("http", "https") and pu.netloc.lower().removeprefix("www.") == host and pu.path not in ("", "/"):
            if not re.search(r"\.(jpe?g|png|gif|svg|css|js|pdf|webp)$", pu.path, re.I):
                g = por_grupo.setdefault(_modelo(pu.path), [])
                if u not in g:
                    g.append(u)
    ordem = sorted((g for g in por_grupo.items() if len(g[1]) >= 2), key=lambda g: -len(g[1]))[:grupos]
    saida = []
    for modelo, links in ordem:
        com, testadas, exemplo = 0, 0, ""
        for u in links[:amostra]:
            try:
                if not permitido(u, client):
                    continue
                ev, _ = contar_jsonld(client.get(u).text[:600_000])
            except httpx.HTTPError:
                continue
            testadas += 1
            if ev:
                com += 1
                exemplo = exemplo or u
            time.sleep(pausa)
        seg = modelo.strip("/").split("/")[0]
        saida.append({"modelo": modelo, "links_na_lista": len(links), "testadas": testadas, "com_evento": com, "exemplo": exemplo,
                      "padrao_sugerido": f"^/{re.escape(seg)}/" if seg != "*" else ""})
    return sorted(saida, key=lambda g: (-g["com_evento"], -g["links_na_lista"]))


def sondar_detalhes(html: str, base_url: str, client, n: int = 5, pausa: float = 1.0) -> dict:
    """Em listagens sem JSON-LD, testa algumas páginas de evento: o JSON-LD costuma estar lá."""
    cands = candidatos_detalhe(html, base_url, n)
    com, exemplos = 0, []
    for u in cands:
        try:
            if not permitido(u, client):
                continue
            ev, _ = contar_jsonld(client.get(u).text[:600_000])
        except httpx.HTTPError:
            continue
        if ev:
            com += 1
            exemplos.append(u)
        time.sleep(pausa)
    return {"detalhes_testados": len(cands), "detalhes_com_evento": com, "detalhes_exemplos": exemplos[:2]}


def testar(f: dict, client: httpx.Client) -> dict:
    r = {"id": f["id"], "categoria": f["categoria"], "url": f["url"], "tipo": f["tipo"], "nota": f.get("nota", "")}
    t0 = time.time()
    try:
        resp = client.get(f["url"])
    except httpx.HTTPError as exc:
        return {**r, "status": None, "resultado": "inacessivel", "detalhe": f"{type(exc).__name__}: {exc}"[:200], "segundos": round(time.time() - t0, 1)}
    corpo = resp.text[:400_000]
    r.update({"status": resp.status_code, "bytes": len(resp.content), "segundos": round(time.time() - t0, 1),
              "content_type": resp.headers.get("content-type", "")[:60]})
    bloqueio = bool(_BLOQUEIO.search(corpo[:20_000])) and resp.status_code != 200 or resp.status_code in (429,) or \
        (resp.status_code == 403 and f["tipo"] == "html")
    if f["tipo"] == "html":
        try:
            r["robots_permite"] = permitido(f["url"], client)
        except Exception:
            r["robots_permite"] = None
        eventos = lugares = 0
        for x in itens_jsonld(corpo):
            t = x.get("@type")
            for tt in (t if isinstance(t, list) else [t]):
                if isinstance(tt, str) and tt.endswith("Event"):
                    eventos += 1
                elif tt in ("Restaurant", "BarOrPub", "FoodEstablishment", "CafeOrCoffeeShop", "NightClub"):
                    lugares += 1
        r.update({"jsonld_eventos": eventos, "jsonld_lugares": lugares, "tem_next_data": "__NEXT_DATA__" in corpo})
        if f["categoria"] == "evento" and not eventos and resp.status_code == 200 and not bloqueio and r.get("robots_permite"):
            r.update(sondar_detalhes(corpo, str(resp.url), client))
    if resp.status_code in (400, 401, 403) and f["tipo"] == "api":
        r["resultado"] = "precisa_de_chave"
    elif bloqueio:
        r["resultado"] = "bloqueado"
    elif resp.status_code >= 400:
        r["resultado"] = f"erro_{resp.status_code}"
    elif f["tipo"] == "html" and r.get("robots_permite") is False:
        r["resultado"] = "robots_proibe"
    elif f["tipo"] == "html" and (r["jsonld_eventos"] or r["jsonld_lugares"]):
        r["resultado"] = "ok_jsonld"
    elif f["tipo"] == "html" and r.get("detalhes_com_evento"):
        r["resultado"] = "ok_via_detalhes"
    elif f["tipo"] == "html":
        r["resultado"] = "abre_sem_dados_estruturados"
    else:
        r["resultado"] = "ok"
    return r


def relatorio_md(resultados: list[dict], quando: str) -> str:
    ordem = {"ok_jsonld": 0, "ok_via_detalhes": 0, "ok": 1, "abre_sem_dados_estruturados": 2, "precisa_de_chave": 3, "robots_proibe": 4, "bloqueado": 5, "inacessivel": 6}
    texto = {"ok_jsonld": "Dá para coletar (JSON-LD)", "ok_via_detalhes": "Dá para coletar seguindo os links dos eventos (modo listagem)", "ok": "Acessível", "abre_sem_dados_estruturados": "Abre, mas sem dados estruturados (precisa de link/seletor)",
             "precisa_de_chave": "Funciona com chave de API", "robots_proibe": "robots.txt proíbe", "bloqueado": "Bloqueia robôs", "inacessivel": "Sem resposta"}
    linhas = [f"# Diagnóstico de fontes\n\nGerado em {quando} (UTC) pelo GitHub Actions. Resultado de acesso por robô; "
              "a decisão de usar cada fonte ainda depende dos termos de uso do site.\n",
              "| Fonte | Categoria | Resultado | HTTP | Eventos JSON-LD | Observação |", "|---|---|---|---|---|---|"]
    for r in sorted(resultados, key=lambda r: (ordem.get(r["resultado"].split("_")[0] if r["resultado"].startswith("erro") else r["resultado"], 5), r["id"])):
        res = texto.get(r["resultado"], r["resultado"].replace("_", " "))
        ev = r.get("jsonld_eventos", "-")
        if r.get("detalhes_testados"):
            ev = f"{ev} (nos detalhes: {r['detalhes_com_evento']}/{r['detalhes_testados']})"
        linhas.append(f"| [{r['id']}]({r['url']}) | {r['categoria']} | {res} | {r.get('status') or '-'} | {ev} | {r.get('nota', '')} |")
    return "\n".join(linhas) + "\n"


def diagnosticar(fontes=None, client=None, pausa=1.0):
    client = client or cliente_http(25)
    out = []
    for f in fontes or FONTES:
        out.append(testar(f, client))
        time.sleep(pausa)
    return out


def salvar(resultados, quando, pasta="data"):
    with open(f"{pasta}/diagnostico_fontes.json", "w", encoding="utf-8") as fh:
        json.dump({"gerado_em": quando, "fontes": resultados}, fh, ensure_ascii=False, indent=1)
    with open("FONTES.md", "w", encoding="utf-8") as fh:
        fh.write(relatorio_md(resultados, quando))
