#!/usr/bin/env python3
"""Baixa os 96 distritos do município de São Paulo (IBGE, malha oficial + nomes) e grava data/geo/distritos_sp.json.gz.
Fonte: servicodados.ibge.gov.br (API de malhas v3 e de localidades v1). Geometria simplificada a ~10 m.
Só o IBGE oficial entra aqui: nada de nomes de bairro inventados."""
import gzip
import json
import sys
from datetime import datetime, timezone

import httpx

COD_SP = "3550308"
URL_MALHA = f"https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{COD_SP}"
URL_NOMES = f"https://servicodados.ibge.gov.br/api/v1/localidades/municipios/{COD_SP}/distritos"
SAIDA = "data/geo/distritos_sp.json.gz"


def simplificar(anel, tol=0.0001):
    """Douglas-Peucker iterativo (tol em graus, ~10 m). Mantém o anel fechado."""
    if len(anel) < 5:
        return anel
    manter = [False] * len(anel)
    manter[0] = manter[-1] = True
    pilha = [(0, len(anel) - 1)]
    while pilha:
        i, j = pilha.pop()
        (x1, y1), (x2, y2) = anel[i], anel[j]
        dx, dy = x2 - x1, y2 - y1
        n = (dx * dx + dy * dy) or 1e-18
        melhor, idx = 0.0, None
        for k in range(i + 1, j):
            x, y = anel[k]
            t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / n))
            d = ((x - (x1 + t * dx)) ** 2 + (y - (y1 + t * dy)) ** 2) ** 0.5
            if d > melhor:
                melhor, idx = d, k
        if idx is not None and melhor > tol:
            manter[idx] = True
            pilha += [(i, idx), (idx, j)]
    return [p for p, m in zip(anel, manter) if m]


def poligonos(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    raise ValueError("geometria inesperada: " + geom["type"])


def main():
    with httpx.Client(timeout=120, follow_redirects=True, headers={"User-Agent": "turiz-cobertura"}) as c:
        nomes = {str(d["id"]): d["nome"] for d in c.get(URL_NOMES).raise_for_status().json()}
        malha = c.get(URL_MALHA, params={"intrarregiao": "distrito", "qualidade": "intermediaria", "formato": "application/vnd.geo+json"}).raise_for_status().json()
    feats = []
    for f in malha["features"]:
        cod = str(f["properties"].get("codarea") or f["properties"].get("id"))
        pols = [[simplificar([[round(x, 5), round(y, 5)] for x, y in anel]) for anel in pol] for pol in poligonos(f["geometry"])]
        feats.append({"codigo": cod, "nome": nomes.get(cod), "poligonos": pols})
    sem_nome = [f["codigo"] for f in feats if not f["nome"]]
    if len(feats) < 90 or sem_nome:
        sys.exit(f"malha inesperada: {len(feats)} distritos, sem nome: {sem_nome}")
    obj = {"fonte": "IBGE — malha municipal v3 (intrarregiao=distrito) + localidades v1", "baixado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "municipio": "São Paulo", "uf": "SP", "distritos": sorted(feats, key=lambda f: f["codigo"])}
    with open(SAIDA, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as g:
        g.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    print(f"{len(feats)} distritos gravados em {SAIDA}")


if __name__ == "__main__":
    main()
