"""Completa endereço de lugares já coletados via geocodificação reversa (Nominatim/OSM).

Regras (para não inventar dado):
  - só preenche campos VAZIOS; nunca sobrescreve o que veio do OSM;
  - bairro e CEP: preenche (dado de área, confiável);
  - rua: só se faltar, sem número (a construção mais próxima pode não ser o lugar);
  - número da casa: nunca é preenchido.
Política da Nominatim: no máximo 1 requisição/segundo, User-Agent identificado.
"""
import time
import httpx

URL = "https://nominatim.openstreetmap.org/reverse"
UA_NOMINATIM = "TurizEnderecosBot/1.0 (https://github.com/felponesx/Turiz; address enrichment)"
PAUSA = 1.1


def extrair(resp: dict) -> dict:
    a = resp.get("address", {}) or {}
    bairro = a.get("suburb") or a.get("neighbourhood") or a.get("quarter") or a.get("city_district") or ""
    return {"bairro": bairro, "cep": a.get("postcode", ""), "rua": a.get("road", "")}


def reverso(lat, lon, client, tentativas=2):
    for t in range(tentativas):
        r = client.get(URL, params={"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 18, "addressdetails": 1, "accept-language": "pt-BR"})
        if r.status_code == 429 and t + 1 < tentativas:
            time.sleep(60)
            continue
        r.raise_for_status()
        return extrair(r.json())


def aplicar(lugar, dados: dict) -> bool:
    """Preenche só o que falta. Retorna True se mudou algo."""
    mudou = False
    if not lugar.bairro and dados["bairro"]:
        lugar.bairro, mudou = dados["bairro"], True
    if not lugar.cep and dados["cep"]:
        lugar.cep, mudou = dados["cep"], True
    if not lugar.endereco and dados["rua"]:
        lugar.endereco, mudou = dados["rua"], True
        lugar.extra = {**(lugar.extra or {}), "endereco_aproximado": True}
    return mudou


def novo_cliente():
    return httpx.Client(timeout=30, headers={"User-Agent": UA_NOMINATIM})
