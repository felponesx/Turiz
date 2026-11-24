"""Territorial: associa cada lugar ao distrito oficial (GeoSampa) pelas coordenadas.
Distrito NÃO é bairro: o bairro fica desconhecido (não há malha oficial de bairros); o nome de bairro escrito no registro vira só 'bairro_declarado'.
Coordenada aproximada (Receita/IBGE) nunca vira 'confirmed'."""
import gzip
import json
import math
import re

from revisao.texto import normalizar_nome

CONFIRMED, PROBABLE, APPROXIMATE, UNKNOWN, CONFLICT = "confirmed", "probable", "approximate", "unknown", "boundary_conflict"
LAT_REF = -23.55
KX = 111320 * math.cos(math.radians(LAT_REF))     # m por grau de longitude
KY = 110574                                        # m por grau de latitude

NOMES_BONITOS = {"SE": "Sé", "REPUBLICA": "República", "CONSOLACAO": "Consolação", "LIBERDADE": "Liberdade", "BRAS": "Brás", "BELEM": "Belém", "BUTANTA": "Butantã",
                 "CAPAO REDONDO": "Capão Redondo", "JABAQUARA": "Jabaquara", "JARAGUA": "Jaraguá", "JACANA": "Jaçanã", "JARDIM ANGELA": "Jardim Ângela", "JAGUARE": "Jaguaré", "JAGUARA": "Jaguara",
                 "BRASILANDIA": "Brasilândia", "CACHOEIRINHA": "Cachoeirinha", "CANGAIBA": "Cangaíba", "CARRAO": "Carrão", "CIDADE LIDER": "Cidade Líder", "FREGUESIA DO O": "Freguesia do Ó",
                 "GRAJAU": "Grajaú", "IPIRANGA": "Ipiranga", "MOOCA": "Mooca", "PEDREIRA": "Pedreira", "SACOMA": "Sacomã", "SAUDE": "Saúde", "SAO LUCAS": "São Lucas", "SAO MATEUS": "São Mateus",
                 "SAO MIGUEL": "São Miguel", "SAO RAFAEL": "São Rafael", "SAO DOMINGOS": "São Domingos", "TUCURUVI": "Tucuruvi", "TREMEMBE": "Tremembé", "VILA SONIA": "Vila Sônia",
                 "VILA CURUCA": "Vila Curuçá", "VILA JACUI": "Vila Jacuí", "AGUA RASA": "Água Rasa", "LIMAO": "Limão", "MORUMBI": "Morumbi", "PARELHEIROS": "Parelheiros", "BARRA FUNDA": "Barra Funda",
                 "CASA VERDE": "Casa Verde", "VILA ANDRADE": "Vila Andrade", "ITAIM BIBI": "Itaim Bibi", "VILA GUILHERME": "Vila Guilherme", "JOSE BONIFACIO": "José Bonifácio", "PERUS": "Perus",
                 "ARTUR ALVIM": "Artur Alvim", "JARDIM SAO LUIS": "Jardim São Luís", "JARDIM HELENA": "Jardim Helena", "PARQUE DO CARMO": "Parque do Carmo", "PONTE RASA": "Ponte Rasa"}


def nome_bonito(oficial: str) -> str:
    if oficial in NOMES_BONITOS:
        return NOMES_BONITOS[oficial]
    peq = {"DE", "DA", "DO", "DAS", "DOS"}
    return " ".join(p.capitalize() if p not in peq else p.lower() for p in oficial.split())


def carregar(caminho="data/geo/distritos_sp.json.gz"):
    with gzip.open(caminho, "rt", encoding="utf-8") as f:
        obj = json.load(f)
    for d in obj["distritos"]:
        d["nome"] = nome_bonito(d["nome_oficial"])
        d["nome_norm"] = normalizar_nome(d["nome_oficial"])
        xs = [p[0] for pol in d["poligonos"] for p in pol[0]]
        ys = [p[1] for pol in d["poligonos"] for p in pol[0]]
        d["bbox"] = (min(xs), min(ys), max(xs), max(ys))
    return obj


def _dentro_anel(x, y, anel):
    dentro = False
    j = len(anel) - 1
    for i in range(len(anel)):
        xi, yi = anel[i]
        xj, yj = anel[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def contem(d, lon, lat) -> bool:
    x0, y0, x1, y1 = d["bbox"]
    if not (x0 <= lon <= x1 and y0 <= lat <= y1):
        return False
    for pol in d["poligonos"]:
        if _dentro_anel(lon, lat, pol[0]) and not any(_dentro_anel(lon, lat, h) for h in pol[1:]):
            return True
    return False


def dist_fronteira_m(d, lon, lat, limite=None) -> float:
    """Menor distância (m) do ponto às bordas do distrito. Para cedo se achar algo abaixo de `limite`."""
    melhor = float("inf")
    for pol in d["poligonos"]:
        for anel in pol:
            for i in range(len(anel) - 1):
                ax, ay = (anel[i][0] - lon) * KX, (anel[i][1] - lat) * KY
                bx, by = (anel[i + 1][0] - lon) * KX, (anel[i + 1][1] - lat) * KY
                dx, dy = bx - ax, by - ay
                n = dx * dx + dy * dy
                t = 0 if n == 0 else max(0, min(1, -(ax * dx + ay * dy) / n))
                dd = math.hypot(ax + t * dx, ay + t * dy)
                if dd < melhor:
                    melhor = dd
                    if limite is not None and melhor < limite:
                        return melhor
    return melhor


def localizar(distritos, lugar, margens=None) -> dict:
    """Retorna {distrito, status, precisao, origem, bairro_declarado, dist_borda_m}. Nunca inventa bairro."""
    margens = margens or {"preciso": 25, "aproximado": 150}
    lat, lon = lugar.get("lat"), lugar.get("lon")
    declarado = (lugar.get("bairro") or "").strip() or None
    base = {"distrito": None, "status": UNKNOWN, "precisao": "nenhuma", "origem": "sem_coordenadas", "bairro": None, "bairro_declarado": declarado}
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or (lat == 0 and lon == 0):
        return base
    aprox = bool((lugar.get("extra") or {}).get("coordenada_aproximada"))
    alvo = next((d for d in distritos if contem(d, lon, lat)), None)
    if alvo is None:
        return {**base, "origem": "fora_dos_distritos_de_sp", "precisao": "aproximada" if aprox else "precisa"}
    prec = "aproximada" if aprox else "precisa"
    borda = dist_fronteira_m(alvo, lon, lat, margens["aproximado" if aprox else "preciso"])
    out = {**base, "distrito": alvo["codigo"], "precisao": prec, "dist_borda_m": round(borda)}
    if borda < margens["aproximado" if aprox else "preciso"]:
        return {**out, "status": CONFLICT, "origem": "perto_da_divisa"}
    if not aprox:
        return {**out, "status": CONFIRMED, "origem": "coordenada_precisa_em_poligono_oficial"}
    nomes = {alvo["nome_norm"], normalizar_nome(alvo.get("subprefeitura") or "")}
    if declarado and re.sub(r"\s+", " ", normalizar_nome(declarado)) in nomes:
        return {**out, "status": PROBABLE, "origem": "coordenada_aproximada+nome_do_bairro_confere_com_o_distrito"}
    return {**out, "status": APPROXIMATE, "origem": "coordenada_aproximada"}
