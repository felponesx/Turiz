"""OpenStreetMap (Overpass): restaurantes e bares do município de São Paulo."""
import time
import httpx

MIRRORS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]
BBOX_SP = (-24.01, -46.83, -23.35, -46.36)  # sul, oeste, norte, leste
TIPO = {"restaurant": "restaurante", "fast_food": "restaurante", "cafe": "restaurante",
        "food_court": "restaurante", "bar": "bar", "pub": "bar", "biergarten": "bar"}


def query(bbox, amenities):
    s, w, n, e = bbox
    return f"""[out:json][timeout:180];
area["name"="São Paulo"]["boundary"="administrative"]["admin_level"="8"]->.sp;
nwr["amenity"~"^({'|'.join(amenities)})$"](area.sp)({s},{w},{n},{e});
out center tags;"""


def grade(bbox=BBOX_SP, linhas=4, colunas=4):
    s, w, n, e = bbox
    dl, dc = (n - s) / linhas, (e - w) / colunas
    for i in range(linhas):
        for j in range(colunas):
            yield (s + i * dl, w + j * dc, s + (i + 1) * dl, w + (j + 1) * dc)


def normalizar(el: dict) -> dict | None:
    t = el.get("tags", {})
    if not t.get("name"):
        return None
    c = el if el["type"] == "node" else el.get("center", {})
    rua = " ".join(x for x in (t.get("addr:street"), t.get("addr:housenumber")) if x)
    return {
        "fonte": "osm", "fonte_id": f'{el["type"]}/{el["id"]}',
        "tipo": TIPO.get(t.get("amenity"), "restaurante"),
        "nome": t["name"], "culinaria": t.get("cuisine", ""),
        "lat": c.get("lat"), "lon": c.get("lon"), "endereco": rua,
        "bairro": t.get("addr:suburb") or t.get("addr:neighbourhood", ""),
        "cep": t.get("addr:postcode", ""),
        "telefone": t.get("phone") or t.get("contact:phone", ""),
        "site": t.get("website") or t.get("contact:website", ""),
        "horario": t.get("opening_hours", ""),
        "extra": {k: t[k] for k in ("contact:instagram", "delivery", "takeaway", "diet:vegan", "diet:vegetarian") if k in t},
    }


def coletar(amenities=("restaurant", "fast_food", "cafe", "bar", "pub"), linhas=4, colunas=4, post=None):
    """Retorna lista de lugares normalizados (sem duplicados)."""
    post = post or _post
    vistos = {}
    for cel in grade(linhas=linhas, colunas=colunas):
        for el in post(query(cel, amenities)).get("elements", []):
            r = normalizar(el)
            if r:
                vistos[r["fonte_id"]] = r
        time.sleep(2)
    return list(vistos.values())


def _post(q, tentativas=6):
    erro = None
    for i in range(tentativas):
        try:
            r = httpx.post(MIRRORS[i % len(MIRRORS)], data={"data": q}, timeout=300,
                           headers={"User-Agent": "guia-sp-api/1.0"})
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as exc:
            erro = exc
            time.sleep(min(60, 5 * (i + 1)))
    raise RuntimeError(f"Overpass indisponível: {erro}")
