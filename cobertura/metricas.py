"""Score de cobertura (0–100), diversidade, concentração e prioridade de coleta. Tudo calculado a partir dos pesos da configuração."""
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone

PESO_STATUS = {"confirmed": 1.0, "probable": 0.7, "boundary_conflict": 0.5, "approximate": 0.3, "unknown": 0.0}
ROTULO_FAIXA = {"muito_boa": "Cobertura muito boa", "boa": "Cobertura boa", "moderada": "Cobertura moderada", "baixa": "Cobertura baixa", "critica": "Cobertura crítica", "desconhecida": "Cobertura desconhecida"}


def faixa(score, cfg):
    return next(nome for corte, nome in cfg["faixas"] if score >= corte)


def idade_dias(iso, agora):
    try:
        t = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return max(0, (agora - t).days)


def diversidade(contagem: Counter, cats_cidade: int, cfg, n_lugares=0, n_especificos=0):
    """Retorna (score 0–100, riqueza, equilíbrio, concentração HHI, predominante). Riqueza só conta categorias com presença mínima;
    especificidade = parte dos lugares que têm alguma categoria além das genéricas (restaurante/bar/lanchonete)."""
    dv = cfg["diversidade"]
    ativos = {k: v for k, v in contagem.items() if v >= dv["presenca_minima"]}
    tot = sum(contagem.values())
    if not tot:
        return 0.0, 0, 0.0, 1.0, None
    shares_all = [v / tot for v in contagem.values() if v > 0]
    hhi = sum(s * s for s in shares_all)
    k = len(ativos)
    even = 0.0
    if k > 1:
        t = sum(ativos.values())
        sh = [v / t for v in ativos.values()]
        even = -sum(s * math.log(s) for s in sh) / math.log(k)
    alvo = max(1, round(dv["riqueza_alvo_fracao"] * cats_cidade))
    espec = (n_especificos / n_lugares) if n_lugares else 0.0
    p = dv["pesos"]
    score = 100 * (p["riqueza"] * min(1.0, k / alvo) + p["equilibrio"] * even + p["especificidade"] * espec)
    top = max(contagem, key=contagem.get)
    return round(score, 1), k, round(even, 3), round(hhi, 3), top


def meta_densidade(dens_por_distrito: list, cfg) -> float:
    v = sorted(d for d in dens_por_distrito if d > 0)
    if not v:
        return 1.0
    p = cfg["densidade"]["meta_percentil"] / 100
    return max(v[min(len(v) - 1, int(p * len(v)))], 0.01)


def score_cobertura(comp: dict, cfg) -> int:
    """comp: componentes 0..1 com as mesmas chaves de pesos_cobertura."""
    pesos = cfg["pesos_cobertura"]
    return max(0, min(100, round(sum(pesos[k] * max(0.0, min(1.0, comp.get(k, 0.0))) for k in pesos))))


def percentil(valor, todos):
    if not todos:
        return 0.0
    return sum(1 for x in todos if x <= valor) / len(todos)


def prioridade(comp: dict, cfg) -> int:
    pesos = cfg["pesos_prioridade"]
    return max(0, min(100, round(sum(pesos[k] * max(0.0, min(1.0, comp.get(k, 0.0))) for k in pesos))))


def scanners_recomendados(m: dict, cfg) -> list:
    ids = []
    if m["status"] in ("critica", "baixa", "desconhecida") or m["ausentes"] >= 3:
        ids.append("geo")
    if m["ausentes"] >= 1:
        ids += ["web", "instagram"]
    if m["componentes"].get("precisao", 1) < 0.5:
        ids.append("location_check")
    if m["confiabilidade_media"] < 70:
        ids += ["revisor", "enriquecimento"]
    vistos = []
    for i in ids:
        if i not in vistos:
            vistos.append(i)
    return [{"id": i, "nome": cfg["scanners"][i]["nome"], "disponivel": cfg["scanners"][i]["disponivel"]} for i in vistos]
