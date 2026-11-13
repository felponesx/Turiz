"""Horários de funcionamento: interpreta `opening_hours` do OpenStreetMap (subconjunto comum).

Só entende regras simples (dias, faixas de hora, "off", "24/7", PH). Se a sintaxe for mais
complexa (semanas, meses, nascer/pôr do sol...), devolve None em vez de adivinhar: nesse
caso o texto bruto continua disponível em `Lugar.horario`.
"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
DIAS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
NOMES = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
_HORA = r"(?:[01]?\d|2[0-4]):[0-5]\d"
_FAIXA = re.compile(rf"^({_HORA})\s*-\s*({_HORA})$")
_DIA = r"(?:Mo|Tu|We|Th|Fr|Sa|Su)"


def _hhmm(s: str) -> str:
    h, m = s.split(":")
    return f"{int(h):02d}:{m}"


def _min(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _dias(txt: str):
    """'Mo-Fr,Su' -> ([0,1,2,3,4,6], feriado?). None se não entender."""
    txt = re.sub(r"\s*([,-])\s*", r"\1", txt.strip())
    idx, feriado = set(), False
    for parte in txt.split(","):
        if parte == "PH":
            feriado = True
            continue
        m = re.fullmatch(rf"({_DIA})(?:-({_DIA}))?", parte)
        if not m:
            return None
        a = DIAS.index(m[1])
        b = DIAS.index(m[2]) if m[2] else a
        i = a
        while True:
            idx.add(i)
            if i == b:
                break
            i = (i + 1) % 7
    return sorted(idx), feriado


def _faixas(txt: str):
    txt = txt.strip()
    if txt.lower() in ("off", "closed"):
        return []
    saida = []
    for parte in txt.split(","):
        m = _FAIXA.match(parte.strip())
        if not m:
            return None
        saida.append([_hhmm(m[1]), _hhmm(m[2])])
    return saida


def parse(oh: str):
    """-> {"dias": {"seg": [["12:00","23:00"]], ...}, "feriados": None|[...], "bruto": oh} ou None."""
    oh = (oh or "").strip()
    if not oh:
        return None
    if oh == "24/7":
        return {"dias": {n: [["00:00", "24:00"]] for n in NOMES}, "feriados": None, "bruto": oh}
    dias, feriados = {}, None
    for regra in (r.strip() for r in oh.split(";")):
        if not regra:
            continue
        toks = regra.split()
        i = next((k for k, t in enumerate(toks) if t[0].isdigit() or t.lower() in ("off", "closed")), None)
        if i is None:
            return None
        alvo = _dias(" ".join(toks[:i])) if i else (list(range(7)), False)
        faixas = _faixas(" ".join(toks[i:]))
        if alvo is None or faixas is None:
            return None
        idx, ph = alvo
        for d in idx:
            dias[d] = faixas
        if ph:
            feriados = faixas
    if not dias and feriados is None:
        return None
    return {"dias": {NOMES[d]: dias.get(d, []) for d in range(7)}, "feriados": feriados, "bruto": oh}


def aberto_agora(h: dict | None, agora: datetime | None = None):
    """True/False, ou None se o horário não foi interpretado. Considera faixas que viram a noite."""
    if not h:
        return None
    agora = (agora or datetime.now(TZ)).astimezone(TZ)
    hoje, ontem = agora.weekday(), (agora.weekday() - 1) % 7
    m = agora.hour * 60 + agora.minute
    for ini, fim in h["dias"][NOMES[hoje]]:
        a, b = _min(ini), _min(fim)
        if (a <= m < b) or (b <= a and m >= a):  # faixa normal ou que começa hoje e vira a noite
            return True
    for ini, fim in h["dias"][NOMES[ontem]]:
        a, b = _min(ini), _min(fim)
        if b <= a and m < b:  # começou ontem e termina hoje de madrugada
            return True
    return False
