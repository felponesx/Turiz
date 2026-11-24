import math
import re
import unicodedata

PALAVRAS_GENERICAS = {"restaurante", "restaurantes", "bar", "bares", "lanchonete", "cafe", "cafeteria", "padaria", "pizzaria", "e", "de", "da", "do", "das", "dos", "the", "ltda", "me"}


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))


def normalizar_nome(nome: str) -> str:
    s = sem_acento(nome).lower().replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(s.split())


def nome_chave(nome: str) -> str:
    """Nome sem palavras genéricas: 'Bar do Zé' e 'Ze' ficam iguais, 'Pizzaria Mario' e 'Mario' também."""
    t = [p for p in normalizar_nome(nome).split() if p not in PALAVRAS_GENERICAS]
    return " ".join(t) or normalizar_nome(nome)


def distancia_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def so_digitos(s) -> str:
    return re.sub(r"\D+", "", str(s or ""))


def numero_do_endereco(end: str) -> str:
    m = re.search(r"(?:,|\s)\s*(\d{1,5})\b", end or "")
    return m.group(1) if m else ""


def rua_do_endereco(end: str) -> str:
    return normalizar_nome(re.split(r",|\s-\s|\d", end or "", maxsplit=1)[0])


def dominio(url: str) -> str:
    m = re.match(r"https?://(?:www\.)?([^/\s?#]+)", (url or "").lower())
    return m.group(1) if m else ""
