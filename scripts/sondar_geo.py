import re, json, httpx
B = "https://wfs.geosampa.prefeitura.sp.gov.br/geoserver/ows"
caps = httpx.get(B, params={"service": "WFS", "request": "GetCapabilities"}, timeout=90).text
nomes = re.findall(r"<Name>([^<]+)</Name>", caps)
print("CAMADAS", [n for n in nomes if re.search(r"distrit|subpref|bairro|zona|regiao|macro|municip|limite", n, re.I)])
r = httpx.get(B, params={"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": "geoportal:distrito_municipal", "outputFormat": "application/json", "srsName": "EPSG:4326"}, timeout=120)
d = r.json(); print("N", len(d["features"]), "bytes", len(r.content))
print("PROPS", json.dumps(d["features"][0]["properties"], ensure_ascii=False))
print("NOMES", sorted(f["properties"].get("nm_distrito_municipal") or str(f["properties"]) for f in d["features"])[:100])
