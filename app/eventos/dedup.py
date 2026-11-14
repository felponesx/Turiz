"""Identificação de eventos duplicados entre fontes.

Regra de ouro: nome parecido NÃO basta. Para considerar o mesmo evento é preciso também a mesma data e o mesmo local (ou
horário praticamente igual com local compatível). Quando há indícios fortes mas faltam provas, o par vai para revisão humana.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo
from .normalizar import norm_nome_evento, norm_texto

FUSO_PADRAO = "America/Sao_Paulo"
GENERICAS_LOCAL = re.compile(r"\b(casa|de|do|da|dos|das|e|the|arena|teatro|espaco|centro|clube|bar|restaurante)\b")


@dataclass
class Resultado:
    decisao: str                   # mesmo | revisar | distinto
    score: float = 0.0
    motivos: list = field(default_factory=list)


def _tokens(s: str) -> set[str]:
    return {t for t in s.split() if len(t) > 2 or t.isdigit()}


def sim_nome(a: str, b: str) -> float:
    """Semelhança entre dois nomes já normalizados (0..1): mistura sequência de letras e conjunto de palavras."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = _tokens(a), _tokens(b)
    jac = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    return 0.5 * SequenceMatcher(None, a, b).ratio() + 0.5 * jac


def _numeros(s: str) -> set[str]:
    return {n for n in re.findall(r"\d+", s) if not (len(n) == 4 and n.startswith(("19", "20")))}   # ignora anos


def data_local(d: datetime | None, fuso: str = "") -> tuple | None:
    if d is None:
        return None
    try:
        z = ZoneInfo(fuso or FUSO_PADRAO)
    except Exception:
        z = ZoneInfo(FUSO_PADRAO)
    l = d.astimezone(z)
    return (l.date(), l.hour * 60 + l.minute)


def dist_m(a_lat, a_lon, b_lat, b_lon) -> float:
    from .geo import distancia_m
    return distancia_m(a_lat, a_lon, b_lat, b_lon)


def sim_local(a: dict, b: dict) -> tuple[str, str]:
    """-> ('forte'|'compativel'|'desconhecido'|'diferente', motivo). a/b: {nome_norm, fonte, fonte_id, lat, lon}."""
    if a.get("fonte_id") and a.get("fonte") == b.get("fonte") and a.get("fonte_id") == b.get("fonte_id"):
        return "forte", "mesmo local (id da fonte)"
    na, nb = GENERICAS_LOCAL.sub(" ", a.get("nome_norm", "")).strip(), GENERICAS_LOCAL.sub(" ", b.get("nome_norm", "")).strip()
    if not na or not nb:
        if a.get("lat") is not None and b.get("lat") is not None and dist_m(a["lat"], a["lon"], b["lat"], b["lon"]) <= 60:
            return "compativel", "coordenadas a menos de 60 m"
        return "desconhecido", "local não informado"
    s = sim_nome(na, nb)
    perto = None
    if a.get("lat") is not None and b.get("lat") is not None:
        perto = dist_m(a["lat"], a["lon"], b["lat"], b["lon"])
    if s >= 0.85 and (perto is None or perto <= 400):
        return "forte", f"mesmo local (nome {s:.2f})"
    if perto is not None and perto <= 150 and s >= 0.5:
        return "forte", f"local a {perto:.0f} m com nome parecido ({s:.2f})"
    if s >= 0.6 or (perto is not None and perto <= 150):
        return "compativel", f"local possivelmente o mesmo (nome {s:.2f})"
    return "diferente", f"locais diferentes (nome {s:.2f})"


def comparar(novo: dict, existente: dict) -> Resultado:
    """novo/existente: {nome_norm, inicio (datetime aware), fuso, local: {...}, organizador_norm}. Devolve a decisão."""
    n1, n2 = novo.get("nome_norm", ""), existente.get("nome_norm", "")
    s_nome = sim_nome(n1, n2)
    if s_nome < 0.6:
        return Resultado("distinto", s_nome, ["nomes diferentes"])
    d1, d2 = data_local(novo.get("inicio"), novo.get("fuso", "")), data_local(existente.get("inicio"), existente.get("fuso", ""))
    if d1 is None or d2 is None:
        return Resultado("distinto", s_nome, ["data incerta em um dos eventos: não dá para afirmar que são o mesmo"])
    if d1[0] != d2[0]:
        return Resultado("distinto", s_nome, ["datas diferentes"])
    motivos = [f"nome {s_nome:.2f}", "mesma data"]
    # hora 00:00 costuma significar "hora não informada": nesse caso só a data é comparável
    hora_ok, hora_proxima = True, False
    if d1[1] != 0 and d2[1] != 0:
        delta = abs(d1[1] - d2[1])
        hora_proxima = delta <= 30
        hora_ok = delta <= 180
        motivos.append(f"horários a {delta} min")
    if not hora_ok:
        return Resultado("distinto", s_nome, motivos + ["sessões em horários diferentes no mesmo dia"])
    loc, motivo_loc = sim_local(novo.get("local") or {}, existente.get("local") or {})
    motivos.append(motivo_loc)
    if loc == "diferente":
        return Resultado("distinto", s_nome, motivos)
    org1, org2 = novo.get("organizador_norm", ""), existente.get("organizador_norm", "")
    if org1 and org1 == org2:
        motivos.append("mesmo organizador")
    nums_diferentes = _numeros(n1) != _numeros(n2)
    if nums_diferentes:
        motivos.append("números diferentes no nome (ex.: 'dia 1' x 'dia 2')")
    score = round(0.55 * s_nome + 0.2 * (1 if loc == "forte" else 0.5 if loc == "compativel" else 0.2) + 0.15 * (1 if hora_proxima else 0.5) + 0.1 * (1 if org1 and org1 == org2 else 0), 3)
    if s_nome >= 0.92 and loc == "forte" and not nums_diferentes:
        return Resultado("mesmo", score, motivos)
    if s_nome >= 0.8 and loc in ("forte", "compativel", "desconhecido"):
        return Resultado("revisar", score, motivos)
    return Resultado("distinto", score, motivos)
