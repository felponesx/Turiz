"""Agendador: decide se uma agenda está "devida". Horários são sempre interpretados em America/Sao_Paulo (configurável).

Tipos de agenda:
  {"tipo": "manual"}                                   nunca dispara sozinha
  {"tipo": "intervalo", "minutos": 360}                a cada N minutos
  {"tipo": "diaria", "horas": ["06:00", "18:30"]}      todo dia nesses horários
  {"tipo": "semanal", "dias": [0, 3], "horas": ["07:00"]}   dias da semana (segunda = 0)
  {"tipo": "unica", "em": "2026-12-01T09:00:00-03:00"} uma vez
  {"tipo": "apos", "bots": ["osm"]}                    quando outro bot terminar (tratado pelo despachante)
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .modelos import parse

JANELA_ATRASO_MIN = 360      # dispositivo parado: ainda executa uma ocorrência atrasada até 6 h; depois só "pula"


def validar(ag: dict) -> list[str]:
    erros = []
    t = (ag or {}).get("tipo")
    if t not in {"manual", "intervalo", "diaria", "semanal", "unica", "apos"}:
        return [f"tipo de agenda desconhecido: {t!r}"]
    if t == "intervalo" and not (isinstance(ag.get("minutos"), int) and 5 <= ag["minutos"] <= 60 * 24 * 30):
        erros.append("intervalo: minutos entre 5 e 43200")
    if t in {"diaria", "semanal"}:
        hs = ag.get("horas") or []
        if not hs or not all(_hora_ok(h) for h in hs):
            erros.append("horas no formato HH:MM")
    if t == "semanal" and not (ag.get("dias") and all(isinstance(d, int) and 0 <= d <= 6 for d in ag["dias"])):
        erros.append("semanal: dias de 0 (segunda) a 6 (domingo)")
    if t == "unica" and parse(ag.get("em")) is None:
        erros.append("unica: informe `em` em ISO 8601")
    if t == "apos" and not ag.get("bots"):
        erros.append("apos: informe os bots")
    return erros


def _hora_ok(h) -> bool:
    try:
        hh, mm = str(h).split(":")
        return 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59
    except ValueError:
        return False


def _ocorrencias(ag, ate_local: datetime, dias_atras: int):
    """Ocorrências (datetime local) de diaria/semanal nos últimos dias, até `ate_local`, em ordem crescente."""
    saida = []
    for d in range(dias_atras, -1, -1):
        dia = (ate_local - timedelta(days=d)).date()
        if ag["tipo"] == "semanal" and dia.weekday() not in ag["dias"]:
            continue
        for h in sorted(ag["horas"]):
            hh, mm = map(int, h.split(":"))
            saida.append(datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=ate_local.tzinfo))
    return [o for o in saida if o <= ate_local]


def avaliar(ag: dict, agora: datetime, ultimo: datetime | None, tz: str = "America/Sao_Paulo"):
    """Retorna (devida, ocorrencia_utc). `ultimo` é a última ocorrência já tratada para esse bot.
    `ocorrencia_utc` deve ser gravada como novo `ultimo` sempre que for > ultimo (mesmo se a execução foi pulada por atraso)."""
    t = (ag or {}).get("tipo", "manual")
    if t in {"manual", "apos"} or validar(ag):
        return False, None
    if t == "intervalo":
        passo = timedelta(minutes=ag["minutos"])
        if ultimo is None or agora >= ultimo + passo:
            return True, agora
        return False, None
    if t == "unica":
        em = parse(ag["em"])
        if agora >= em and (ultimo is None or ultimo < em):
            return (agora - em).total_seconds() / 60 <= JANELA_ATRASO_MIN, em
        return False, None
    local = agora.astimezone(ZoneInfo(tz))
    ocs = _ocorrencias(ag, local, 8)
    if not ocs:
        return False, None
    oc = ocs[-1].astimezone(agora.tzinfo)
    if ultimo is not None and oc <= ultimo:
        return False, None
    return (agora - oc).total_seconds() / 60 <= JANELA_ATRASO_MIN, oc


def proxima(ag: dict, agora: datetime, ultimo: datetime | None, tz: str = "America/Sao_Paulo"):
    """Próxima execução prevista (UTC) para exibir no painel; None se não houver (manual/apos)."""
    t = (ag or {}).get("tipo", "manual")
    if t in {"manual", "apos"} or validar(ag):
        return None
    if t == "intervalo":
        return ultimo + timedelta(minutes=ag["minutos"]) if ultimo else None     # estável entre ciclos (não muda a cada 10 min)
    if t == "unica":
        em = parse(ag["em"])
        return em if (ultimo is None or ultimo < em) else None
    local = agora.astimezone(ZoneInfo(tz))
    for d in range(0, 9):
        dia = (local + timedelta(days=d)).date()
        if t == "semanal" and dia.weekday() not in ag["dias"]:
            continue
        for h in sorted(ag["horas"]):
            hh, mm = map(int, h.split(":"))
            cand = datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=local.tzinfo)
            if cand > local:
                return cand.astimezone(agora.tzinfo)
    return None


def descrever(ag: dict) -> str:
    """Texto curto em português para o painel."""
    t = (ag or {}).get("tipo", "manual")
    nomes = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
    if t == "manual":
        return "Só manual"
    if t == "intervalo":
        m = ag.get("minutos", 0)
        return f"A cada {m // 60} h" if m % 60 == 0 and m >= 60 else f"A cada {m} min"
    if t == "diaria":
        return "Todo dia " + ", ".join(ag.get("horas", []))
    if t == "semanal":
        return ", ".join(nomes[d] for d in ag.get("dias", [])) + " " + ", ".join(ag.get("horas", []))
    if t == "unica":
        return "Uma vez em " + str(ag.get("em"))
    if t == "apos":
        return "Depois de " + ", ".join(ag.get("bots", []))
    return "?"
