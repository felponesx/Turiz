#!/usr/bin/env python3
"""Baixa os 96 distritos oficiais de São Paulo (GeoSampa/Prefeitura, WFS) e grava data/geo/distritos_sp.json.gz.
Geometria simplificada a ~10 m. Só dado oficial entra aqui: nada de nomes de bairro inventados."""
import gzip
import json
import sys
from datetime import datetime, timezone

import httpx

WFS = "https://wfs.geosampa.prefeitura.sp.gov.br/geoserver/ows"
SAIDA = "data/geo/distritos_sp.json.gz"


def wfs(c, camada):
    r = c.get(WFS, params={"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": camada, "outputFormat": "application/json", "srsName": "EPSG:4326"})
    return r.raise_for_status().json()["features"]


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
    with httpx.Client(timeout=180, follow_redirects=True, headers={"User-Agent": "turiz-cobertura"}) as c:
        dist = wfs(c, "geoportal:distrito_municipal")
        subs = {f["properties"]["cd_identificador_subprefeitura"]: f["properties"] for f in wfs(c, "geoportal:subprefeitura")}
    feats = []
    for f in dist:
        p = f["properties"]
        pols = [[simplificar([[round(x, 5), round(y, 5)] for x, y in anel]) for anel in pol] for pol in poligonos(f["geometry"])]
        sub = subs.get(p.get("cd_identificador_subprefeitura")) or {}
        feats.append({"codigo": str(p["cd_distrito_municipal"]), "nome_oficial": p["nm_distrito_municipal"], "sigla": p.get("sg_distrito_municipal"),
                      "zona": p.get("nm_regiao_05"), "subprefeitura": sub.get("nm_subprefeitura"), "area_km2": p.get("qt_area_quilometro"), "poligonos": pols})
    zonas = {f["zona"] for f in feats}
    if len(feats) != 96 or not zonas <= {"Centro", "Norte", "Sul", "Leste", "Oeste"} or None in zonas:
        sys.exit(f"dados inesperados: {len(feats)} distritos, zonas {zonas}")
    obj = {"fonte": "Prefeitura de São Paulo — GeoSampa (WFS): distrito_municipal e subprefeitura; zona = campo oficial nm_regiao_05",
           "baixado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"), "municipio": "São Paulo", "uf": "SP",
           "distritos": sorted(feats, key=lambda f: f["codigo"])}
    with open(SAIDA, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as g:
        g.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    print(f"{len(feats)} distritos; zonas {sorted(zonas)}; gravados em {SAIDA}")


if __name__ == "__main__":
    main()
