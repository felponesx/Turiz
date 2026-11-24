"""Deduplicador de lugares. Nunca une unidades diferentes de uma franquia e nunca apaga nada:
só relaciona o duplicado ao registro canônico (IDs, histórico e origem preservados)."""
from collections import defaultdict
from difflib import SequenceMatcher

from .texto import distancia_m, nome_chave, numero_do_endereco, rua_do_endereco, so_digitos, dominio

CELULA = 0.001           # ~110 m
RAIO_MAX_M = 150
RAIO_CONFIRMADO_M = 60
SIM_CONFIRMADO = 0.97
SIM_POSSIVEL = 0.86
MIN_UNIDADES_FRANQUIA = 4  # mesmo nome em ≥4 pontos diferentes = rede/franquia
PREFERENCIA_FONTE = {"google": 0, "osm": 1, "sites": 2, "receita": 3}

CONFIRMADO, POSSIVEL, UNIDADE = "duplicado_confirmado", "possivel_duplicado", "unidade_diferente"


def _aprox(l):
    return bool((l.get("extra") or {}).get("coordenada_aproximada"))


def _sim(a, b):
    return 1.0 if a == b else SequenceMatcher(None, a, b).ratio()


def franquias(lugares):
    """Nomes que aparecem em muitos pontos diferentes (rede)."""
    c = defaultdict(int)
    for l in lugares:
        c[nome_chave(l["nome"])] += 1
    return {k for k, v in c.items() if v >= MIN_UNIDADES_FRANQUIA and k}


def comparar(a, b, rede):
    """Classifica um par de lugares próximos. Retorna (tipo, motivo, distância, similaridade) ou None."""
    na, nb = nome_chave(a["nome"]), nome_chave(b["nome"])
    if not na or not nb:
        return None
    d = distancia_m(a["lat"], a["lon"], b["lat"], b["lon"])
    sim = _sim(na, nb)
    if sim < SIM_POSSIVEL and not (na in nb or nb in na) or d > RAIO_MAX_M:
        return None
    tel_a, tel_b = so_digitos(a.get("telefone")), so_digitos(b.get("telefone"))
    mesmo_contato = (len(tel_a) >= 8 and tel_a[-8:] == tel_b[-8:]) or (dominio(a.get("site")) and dominio(a.get("site")) == dominio(b.get("site")) and na == nb and not rede)
    num_a, num_b = numero_do_endereco(a.get("endereco")), numero_do_endereco(b.get("endereco"))
    rua_igual = bool(rua_do_endereco(a.get("endereco"))) and rua_do_endereco(a.get("endereco")) == rua_do_endereco(b.get("endereco"))
    mesmo_cep = bool(a.get("cep")) and a.get("cep") == b.get("cep")
    enderecos_diferentes = bool(num_a and num_b and num_a != num_b and rua_igual)
    aproximado = _aprox(a) or _aprox(b)
    if enderecos_diferentes:
        return UNIDADE, "números diferentes na mesma rua", d, sim
    nome_igual = sim >= SIM_CONFIRMADO
    if mesmo_contato and nome_igual:
        return CONFIRMADO, "mesmo nome e mesmo telefone/site", d, sim
    if nome_igual and not rede:
        if d <= RAIO_CONFIRMADO_M and (not aproximado or mesmo_cep or rua_igual):
            return CONFIRMADO, "mesmo nome no mesmo ponto", d, sim
        if num_a and num_a == num_b and rua_igual:
            return CONFIRMADO, "mesmo nome, rua e número", d, sim
    if rede and nome_igual and not (num_a and num_a == num_b and rua_igual):
        return UNIDADE, "rede com várias unidades: não unir sem mesmo endereço", d, sim
    return POSSIVEL, ("nome parecido e muito perto" if not nome_igual else "mesmo nome perto, sem endereço que confirme"), d, sim


def _escolher_canonico(a, b):
    ka = (PREFERENCIA_FONTE.get(a["fonte"], 9), _aprox(a), -len([v for v in (a.get("endereco"), a.get("cep"), a.get("bairro"), a.get("telefone"), a.get("site")) if v]), a["id"])
    kb = (PREFERENCIA_FONTE.get(b["fonte"], 9), _aprox(b), -len([v for v in (b.get("endereco"), b.get("cep"), b.get("bairro"), b.get("telefone"), b.get("site")) if v]), b["id"])
    return (a, b) if ka <= kb else (b, a)


def encontrar(lugares, progresso=None):
    """Lista de pares relacionados. Cada item: dict com a, b, tipo, motivo, dist_m, sim e canonico/duplicado (só para confirmados)."""
    rede = franquias(lugares)
    celulas = defaultdict(list)
    for l in lugares:
        if l.get("lat") is None or l.get("lon") is None:
            continue
        celulas[(round(l["lat"] / CELULA), round(l["lon"] / CELULA))].append(l)
    pares, total = [], len(celulas)
    for i, ((cx, cy), membros) in enumerate(celulas.items()):
        if progresso and i % 500 == 0:
            progresso(i, total)
        vizinhos = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                vizinhos.extend(celulas.get((cx + dx, cy + dy), ()))
        for a in membros:
            for b in vizinhos:
                if a["id"] >= b["id"]:
                    continue
                r = comparar(a, b, nome_chave(a["nome"]) in rede or nome_chave(b["nome"]) in rede)
                if not r:
                    continue
                tipo, motivo, d, sim = r
                item = {"a": a["id"], "b": b["id"], "tipo": tipo, "motivo": motivo, "dist_m": round(d), "sim": round(sim, 2)}
                if tipo == CONFIRMADO:
                    can, dup = _escolher_canonico(a, b)
                    item["canonico"], item["duplicado"] = can["id"], dup["id"]
                    item["fontes_distintas"] = a["fonte"] != b["fonte"]
                pares.append(item)
    if progresso:
        progresso(total, total)
    return pares


def resolver(pares):
    """Mapa duplicado -> canônico (cadeias resolvidas, sem ciclos)."""
    pai = {}
    for p in pares:
        if p["tipo"] == CONFIRMADO:
            pai.setdefault(p["duplicado"], p["canonico"])
    def raiz(x, vistos=()):
        while x in pai and x not in vistos:
            vistos += (x,)
            x = pai[x]
        return x
    return {d: raiz(d) for d in pai if raiz(d) != d}
