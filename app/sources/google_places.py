"""Google Places API (New) - Text Search. Pago; exige GOOGLE_PLACES_API_KEY.

Cada busca retorna no máximo 60 resultados, por isso varremos a cidade em grade
de círculos e várias consultas (restaurante, bar...).
"""
import os
import httpx

URL = "https://places.googleapis.com/v1/places:searchText"
CAMPOS = ("places.id,places.displayName,places.formattedAddress,places.location,places.rating,"
          "places.nationalPhoneNumber,places.websiteUri,places.primaryType,"
          "places.regularOpeningHours.weekdayDescriptions,nextPageToken")


def normalizar(p: dict, tipo: str) -> dict:
    loc = p.get("location", {})
    return {
        "fonte": "google", "fonte_id": p["id"], "tipo": tipo,
        "nome": p.get("displayName", {}).get("text", ""),
        "culinaria": p.get("primaryType", ""),
        "lat": loc.get("latitude"), "lon": loc.get("longitude"),
        "endereco": p.get("formattedAddress", ""),
        "telefone": p.get("nationalPhoneNumber", ""), "site": p.get("websiteUri", ""),
        "horario": "; ".join(p.get("regularOpeningHours", {}).get("weekdayDescriptions", [])),
        "nota": p.get("rating"),
    }


def coletar(centros, raio_m=1500, consultas=(("restaurante em São Paulo", "restaurante"), ("bar em São Paulo", "bar")),
            chave=None, client=None):
    chave = chave or os.getenv("GOOGLE_PLACES_API_KEY")
    if not chave:
        raise RuntimeError("Defina GOOGLE_PLACES_API_KEY")
    client = client or httpx.Client(timeout=30)
    vistos = {}
    for lat, lon in centros:
        for texto, tipo in consultas:
            token = None
            for _ in range(3):  # 3 páginas x 20 = 60
                corpo = {"textQuery": texto, "pageSize": 20, "languageCode": "pt-BR",
                         "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": raio_m}}}
                if token:
                    corpo["pageToken"] = token
                r = client.post(URL, json=corpo, headers={"X-Goog-Api-Key": chave, "X-Goog-FieldMask": CAMPOS})
                r.raise_for_status()
                d = r.json()
                for p in d.get("places", []):
                    vistos[p["id"]] = normalizar(p, tipo)
                token = d.get("nextPageToken")
                if not token:
                    break
    return list(vistos.values())
