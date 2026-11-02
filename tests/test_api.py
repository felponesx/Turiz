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


def test_geo_e_front():
    assert isinstance(c.get("/lugares/geo").json(), list)
    r = c.get("/")
    assert r.status_code == 200 and "Turiz" in r.text


def test_imagens_commons_e_site():
    import httpx
    from app.sources import imagens

    def handler(req):
        u = str(req.url)
        if "wikidata.org" in u:
            return httpx.Response(200, json={"entities": {"Q1": {"claims": {"P18": [{"mainsnak": {"datavalue": {"value": "Foto bar.jpg"}}}]}}}})
        if "commons.wikimedia.org" in u:
            pages = {"1": {"title": "File:Foto bar.jpg", "imageinfo": [{"url": "https://u/f.jpg", "thumburl": "https://u/t.jpg", "width": 10, "height": 5,
                     "descriptionurl": "https://c/File", "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}, "Artist": {"value": "<a>Ana</a>"}}}]},
                     "2": {"title": "File:Fechada.jpg", "imageinfo": [{"url": "https://u/g.jpg", "extmetadata": {"LicenseShortName": {"value": "All rights reserved"}}}]}}
            return httpx.Response(200, json={"query": {"pages": pages}})
        return httpx.Response(404)
    cli = httpx.Client(transport=httpx.MockTransport(handler))
    els = {"elements": [
        {"type": "node", "id": 1, "tags": {"name": "Bar A", "wikidata": "Q1"}},
        {"type": "way", "id": 2, "tags": {"name": "B", "wikimedia_commons": "File:Fechada.jpg"}},
        {"type": "node", "id": 3, "tags": {"name": "C", "image": "https://x.com/a.jpg"}}]}
    r = imagens.coletar_commons(post=lambda q: els, client=cli)
    por = {(x["lugar_fonte_id"], x["fonte"]): x for x in r}
    assert por[("node/1", "commons")]["status"] == "aprovada" and por[("node/1", "commons")]["autor"] == "Ana"
    assert por[("way/2", "commons")]["status"] == "pendente"
    assert por[("node/3", "osm_image")]["status"] == "pendente"

    html = '<meta property="og:image" content="/img/capa.jpg">'
    assert imagens.og_image(html, "https://site.com/x") == "https://site.com/img/capa.jpg"


def test_api_imagens_e_moderacao():
    reg = {"fonte": "osm", "fonte_id": "node/99", "tipo": "bar", "nome": "Bar Foto"}
    h = {"x-api-key": "k"}
    c.post("/ingest/lugares", json=[reg], headers=h)
    from app.db import SessionLocal
    from app.ingest import upsert
    from app.models import Imagem, Lugar
    from sqlalchemy import select
    with SessionLocal() as db:
        lid = db.scalar(select(Lugar.id).where(Lugar.fonte_id == "node/99"))
        upsert(db, Imagem, [{"lugar_fonte": "osm", "lugar_fonte_id": "node/99", "fonte": "site", "url": "https://a/1.jpg", "status": "pendente"}])
        iid = db.scalar(select(Imagem.id))
    assert c.get(f"/lugares/{lid}/imagens").json() == []
    assert len(c.get(f"/lugares/{lid}/imagens", params={"status": "todas"}).json()) == 1
    assert c.patch(f"/imagens/{iid}", params={"status": "aprovada"}).status_code == 401
    assert c.patch(f"/imagens/{iid}", params={"status": "aprovada"}, headers=h).json()["status"] == "aprovada"
    assert len(c.get(f"/lugares/{lid}/imagens").json()) == 1
