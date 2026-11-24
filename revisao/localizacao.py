"""Location Check: valida coordenadas e endereço sem inventar nada. Só aponta problemas."""
import re

# caixa aproximada do município de São Paulo (folga pequena); fora dela = fora da área de cobertura
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = -24.05, -23.30, -46.90, -46.30
FLAGS = {
    "coordenadas_invalidas": "Coordenadas ausentes ou impossíveis",
    "fora_da_area": "Fora da área de cobertura (município de São Paulo)",
    "coordenada_aproximada": "Coordenada aproximada (pelo CEP/centro da área)",
    "endereco_incompleto": "Sem rua no endereço",
    "sem_numero": "Endereço sem número",
    "sem_bairro": "Sem bairro",
    "sem_cep": "Sem CEP",
    "cep_invalido": "CEP em formato inválido",
    "cep_fora_de_sp": "CEP não é de São Paulo capital",
}
# gravidade: o que impede de considerar a localização validada
GRAVES = {"coordenadas_invalidas", "fora_da_area", "cep_invalido", "cep_fora_de_sp"}


def cep_de_sp_capital(cep: str) -> bool:
    n = int(cep[:5])
    return 1000 <= n <= 5999 or 8000 <= n <= 8499


def checar(l) -> list:
    f = []
    lat, lon = l.get("lat"), l.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or (lat == 0 and lon == 0) or abs(lat) > 90 or abs(lon) > 180:
        f.append("coordenadas_invalidas")
    elif not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        f.append("fora_da_area")
    if (l.get("extra") or {}).get("coordenada_aproximada"):
        f.append("coordenada_aproximada")
    end = (l.get("endereco") or "").strip()
    if not end:
        f.append("endereco_incompleto")
    elif not re.search(r"\d", end):
        f.append("sem_numero")
    if not (l.get("bairro") or "").strip():
        f.append("sem_bairro")
    cep = re.sub(r"\D", "", l.get("cep") or "")
    if not cep:
        f.append("sem_cep")
    elif len(cep) != 8:
        f.append("cep_invalido")
    elif not cep_de_sp_capital(cep):
        f.append("cep_fora_de_sp")
    return f


def verificar(lugares) -> dict:
    """id -> lista de flags (só quem tem problema)."""
    return {l["id"]: fl for l in lugares if (fl := checar(l))}
