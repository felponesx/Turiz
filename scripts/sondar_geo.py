import httpx
C = {
 "geosampa": "https://wfs.geosampa.prefeitura.sp.gov.br/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=geoportal:distrito_municipal&outputFormat=application/json&srsName=EPSG:4326&maxFeatures=3",
 "geosampa_caps": "https://wfs.geosampa.prefeitura.sp.gov.br/geoserver/ows?service=WFS&request=GetCapabilities",
 "ibge_dist": "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/3550308?intrarregiao=distrito&formato=application/vnd.geo+json",
 "ibge_dist2": "https://servicodados.ibge.gov.br/api/v3/malhas/distritos/355030801?formato=application/vnd.geo+json",
 "ibge_dist3": "https://servicodados.ibge.gov.br/api/v3/malhas/distritos?formato=application/vnd.geo+json&intrarregiao=municipio",
}
for k, u in C.items():
    try:
        r = httpx.get(u, timeout=90, follow_redirects=True)
        print(k, r.status_code, len(r.content), r.text[:300].replace("\n", " "))
    except Exception as e:
        print(k, "ERRO", repr(e)[:200])
