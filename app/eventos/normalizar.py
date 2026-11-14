"""Normalização de texto e de status."""
import re
import unicodedata

_PREFIXOS = re.compile(r"^(ingressos?|tickets?)\s+(para|de|do|da)\s+", re.I)


def norm_texto(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def norm_nome_evento(s: str) -> str:
    """Nome comparável entre fontes: sem acento/pontuação e sem o prefixo 'Ingressos para'."""
    return norm_texto(_PREFIXOS.sub("", (s or "").strip()))


_STATUS = {
    "onsale": "agendado", "offsale": "agendado", "scheduled": "agendado", "agendado": "agendado", "eventscheduled": "agendado",
    "eventmovedonline": "agendado",
    "cancelled": "cancelado", "canceled": "cancelado", "cancelado": "cancelado", "eventcancelled": "cancelado",
    "postponed": "adiado", "adiado": "adiado", "eventpostponed": "adiado",
    "rescheduled": "remarcado", "remarcado": "remarcado", "eventrescheduled": "remarcado",
}


def status_de(raw: str) -> str:
    """Mapeia o status informado pela fonte. Vazio = agendado; valor desconhecido = 'desconhecido' (o bruto fica registrado)."""
    k = re.sub(r"^https?://schema\.org/", "", (raw or "").strip()).lower()
    if not k:
        return "agendado"
    return _STATUS.get(k, "desconhecido")
