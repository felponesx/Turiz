import os
os.environ["DATABASE_URL"] = "sqlite:///./teste.db"
os.environ["API_KEY"] = "k"
from fastapi.testclient import TestClient
from app.main import app
from app.sources import osm, sites, google_places

c = TestClient(app)


def test_osm_normalizar():
    el = {"type": "way", "id": 5, "center": {"lat": -23.5, "lon": -46.6},
          "tags": {"name": "Pizzaria X", "amenity": "restaurant", "cuisine": "pizza", "addr:street": "Rua A", "addr:housenumber": "10"}}
    r = osm.normalizar(el)
    assert r["fonte_id"] == "way/5" and r["tipo"] == "restaurante" and r["endereco"] == "Rua A 10"
    assert osm.normalizar({"type": "node", "id": 1, "tags": {"amenity": "bar"}}) is None


def test_jsonld_eventos_e_lugares():
    html = '''<script type="application/ld+json">[{"@type":"Event","name":"Show","startDate":"2026-12-01T20:00:00-03:00",
      "location":{"name":"Casa","address":{"streetAddress":"Rua B 1","addressLocality":"São Paulo"}}},
      {"@type":"BarOrPub","name":"Bar Y","address":"Rua C"}]</script>'''
    l, e = sites.extrair(html, "https://x.com/p", "evento")
    assert e[0]["titulo"] == "Show" and e[0]["local_nome"] == "Casa" and e[0]["inicio"].year == 2026
    assert l[0]["tipo"] == "bar"


def test_google_normalizar():
    r = google_places.normalizar({"id": "g1", "displayName": {"text": "Z"}, "location": {"latitude": 1, "longitude": 2}}, "bar")
    assert r["fonte_id"] == "g1" and r["lat"] == 1


def test_ingest_e_consulta():
    reg = {"fonte": "bot", "fonte_id": "1", "tipo": "bar", "nome": "Bar do Zé", "bairro": "Pinheiros"}
    assert c.post("/ingest/lugares", json=[reg]).status_code == 401
    h = {"x-api-key": "k"}
    assert c.post("/ingest/lugares", json=[reg], headers=h).json() == {"novos": 1, "atualizados": 0}
    assert c.post("/ingest/lugares", json=[reg], headers=h).json() == {"novos": 0, "atualizados": 1}
    j = c.get("/lugares", params={"tipo": "bar", "bairro": "pinh"}).json()
    assert j["total"] == 1 and j["itens"][0]["nome"] == "Bar do Zé"
    assert c.get("/eventos").json()["total"] == 0
    assert c.get("/health").json()["ok"]
