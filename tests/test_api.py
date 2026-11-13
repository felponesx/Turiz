import os
if os.path.exists("teste.db"):  # banco de teste limpo a cada rodada
    os.remove("teste.db")
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


def test_enderecos_nao_sobrescreve_nem_inventa_numero():
    import httpx
    from types import SimpleNamespace
    from app.sources import enderecos
    d = enderecos.extrair({"address": {"road": "Rua A", "house_number": "99", "suburb": "Pinheiros", "postcode": "05428-000"}})
    assert d == {"bairro": "Pinheiros", "cep": "05428-000", "rua": "Rua A"}
    l = SimpleNamespace(bairro="", cep="01000-000", endereco="", extra={})
    assert enderecos.aplicar(l, d) is True
    assert l.bairro == "Pinheiros" and l.cep == "01000-000"      # cep existente preservado
    assert l.endereco == "Rua A" and "99" not in l.endereco      # sem número da casa
    assert l.extra["endereco_aproximado"] is True
    l2 = SimpleNamespace(bairro="Moema", cep="1", endereco="Rua B 5", extra={})
    assert enderecos.aplicar(l2, d) is False and l2.endereco == "Rua B 5"
    cli = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"address": {"suburb": "Mooca"}})))
    assert enderecos.reverso(-23.5, -46.6, cli)["bairro"] == "Mooca"


def test_instagram_vinculos_e_verificacao():
    import httpx
    from app.sources import instagram as ig
    assert ig.normalizar_usuario("https://www.instagram.com/Casa.do.Porco/?hl=pt") == "casa.do.porco"
    assert ig.normalizar_usuario("@cincopizzas") == "cincopizzas"
    assert ig.normalizar_usuario("https://instagram.com/p/ABC123/") is None
    html = '<a href="https://instagram.com/bar_do_ze/">ig</a><a href="https://instagram.com/p/xyz">post</a><a href="/contato">c</a>'
    assert ig.usuarios_do_html(html) == ["bar_do_ze"]
    lugar = {"fonte": "osm", "fonte_id": "node/1", "extra": {"contact:instagram": "barzinho"}}
    v = ig.vinculos_osm(lugar)[0]
    assert v["status"] == "confirmado" and v["origem"] == "osm_tag" and v["url"].endswith("/barzinho/")
    assert ig.vinculos_osm({"fonte": "osm", "fonte_id": "node/2", "extra": {}}) == []
    resp = {"business_discovery": {"username": "barzinho_sp", "name": "Barzinho SP", "website": "https://www.barzinho.com.br/", "followers_count": 1200}}
    cli = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=resp)))
    r = ig.verificar("barzinho_sp", "Barzinho", "barzinho.com.br", "t", "1", cli)
    assert r["confere"] and r["site_confere"] and r["seguidores"] == 1200
    cli2 = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400, json={"error": {}})))
    assert ig.verificar("pessoal", "X", "", "t", "1", cli2) is None
    r3 = ig.verificar("outro", "Restaurante Totalmente Diferente", "", "t", "1", httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"business_discovery": {"username": "zzzqqq", "name": "Loja de Pneus"}}))))
    assert r3["confere"] is False
