import os
import uuid
os.environ.setdefault("DATABASE_URL", "sqlite:///./teste.db")
os.environ.setdefault("API_KEY", "k")
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.db import Base, SessionLocal, engine
from app.ingest import upsert
from app.main import app
from app.models import Avaliacao, Cardapio, Evento, Lugar
from app.sources import sites, ticketmaster, vincular

c = TestClient(app)
H = {"x-api-key": os.environ["API_KEY"]}


def test_jsonld_evento_com_preco_categoria_e_ingresso():
    html = '''<script type="application/ld+json">{"@type":"MusicEvent","name":"Show","startDate":"2026-12-05T21:00:00-03:00",
      "image":["https://x.com/a.jpg"],"location":{"name":"Casa X","geo":{"latitude":-23.55,"longitude":-46.63}},
      "offers":[{"@type":"Offer","price":"80.00","url":"https://x.com/comprar"},{"@type":"Offer","price":"120","url":"https://x.com/vip"}]}</script>
      <script type="application/ld+json">{"@type":"Event","name":"Aberto","offers":{"price":"0"}}</script>'''
    _, ev = sites.extrair(html, "https://x.com/p", "evento")
    show = next(e for e in ev if e["titulo"] == "Show")
    assert (show["categoria"], show["preco_min"], show["gratuito"]) == ("musica", 80.0, False)
    assert show["ingresso_url"] == "https://x.com/comprar" and show["imagem_url"] == "https://x.com/a.jpg"
    assert next(e for e in ev if e["titulo"] == "Aberto")["gratuito"] is True


LUG = [{"fonte": "osm", "fonte_id": "node/1", "nome": "Bar do Zé", "lat": -23.5500, "lon": -46.6300, "_n": vincular.norm("Bar do Zé")},
       {"fonte": "osm", "fonte_id": "node/2", "nome": "Bar do Zeca", "lat": -23.5600, "lon": -46.6400, "_n": vincular.norm("Bar do Zeca")}]


def test_vincular_evento_ao_lugar_certo_e_nao_adivinha():
    ok = vincular.casar({"local_nome": "Bar do Ze", "lat": -23.5501, "lon": -46.6301}, LUG)
    assert ok["fonte_id"] == "node/1"                                       # sem acento, ~15 m de distância
    assert vincular.casar({"local_nome": "Bar do Zé", "lat": -23.60, "lon": -46.70}, LUG) is None   # longe demais
    assert vincular.casar({"local_nome": "Casa de Shows Outra", "lat": -23.5500, "lon": -46.6300}, LUG) is None  # perto, mas outro nome
    assert vincular.casar({"local_nome": "Bar do Zé"}, LUG)["fonte_id"] == "node/1"   # sem coordenada: nome idêntico
    assert vincular.casar({"local_nome": "Bar do"}, LUG) is None            # sem coordenada: nome vago não liga


def test_ticketmaster_normalizar():
    ev = {"id": "T1", "name": "Banda X", "url": "https://tm.com/e", "dates": {"start": {"dateTime": "2026-12-10T22:00:00Z"}},
          "images": [{"url": "https://i/p.jpg", "width": 200}, {"url": "https://i/g.jpg", "width": 1024}],
          "classifications": [{"segment": {"name": "Music"}}], "priceRanges": [{"min": 90.0, "max": 300.0}],
          "_embedded": {"venues": [{"name": "Casa Y", "address": {"line1": "Rua A, 1"}, "city": {"name": "São Paulo"},
                                    "location": {"latitude": "-23.5", "longitude": "-46.6"}}]}}
    r = ticketmaster.normalizar(ev)
    assert (r["fonte"], r["categoria"], r["preco_min"], r["imagem_url"]) == ("ticketmaster", "musica", 90.0, "https://i/g.jpg")
    assert r["local_nome"] == "Casa Y" and r["lat"] == -23.5 and r["inicio"].year == 2026
    assert ticketmaster.coletar(chave="") == []   # sem chave a fonte é ignorada


def _semear():
    """Cria um lugar novo (id único), para o teste não depender de execuções anteriores."""
    Base.metadata.create_all(engine)
    fid = "node/" + uuid.uuid4().hex[:10]
    with SessionLocal() as db:
        upsert(db, Lugar, [{"fonte": "osm", "fonte_id": fid, "tipo": "bar", "nome": "Bar Endpoint", "horario": "Mo-Su 00:00-24:00"}])
        lid = db.scalar(select(Lugar.id).where(Lugar.fonte_id == fid))
        upsert(db, Cardapio, [{"lugar_fonte": "osm", "lugar_fonte_id": fid, "url": "https://b.com/cardapio", "status": "provavel"}])
        futuro = datetime.now(timezone.utc) + timedelta(days=3)
        upsert(db, Evento, [{"fonte": "t", "fonte_id": fid + "e1", "titulo": "Show Futuro", "inicio": futuro, "lugar_fonte": "osm", "lugar_fonte_id": fid},
                            {"fonte": "t", "fonte_id": fid + "e2", "titulo": "Show Passado", "inicio": futuro - timedelta(days=30), "lugar_fonte": "osm", "lugar_fonte_id": fid}])
    return lid


def test_endpoints_do_lugar():
    lid = _semear()
    d = c.get(f"/lugares/{lid}").json()
    assert d["aberto_agora"] is True and d["horario_estruturado"]["dias"]["seg"] == [["00:00", "24:00"]]
    assert [x["url"] for x in c.get(f"/lugares/{lid}/cardapios").json()] == ["https://b.com/cardapio"]
    assert [e["titulo"] for e in c.get(f"/lugares/{lid}/eventos").json()] == ["Show Futuro"]   # só os futuros
    assert lid in [i["id"] for i in c.get("/lugares", params={"aberto_agora": "true"}).json()["itens"]]
    assert lid not in [i["id"] for i in c.get("/lugares", params={"aberto_agora": "false"}).json()["itens"]]
    assert c.get("/lugares/999999/cardapios").status_code == 404


def test_avaliacoes_fluxo_completo():
    lid = _semear()
    ref = uuid.uuid4().hex
    corpo = {"lugar_id": lid, "experiencia_ref": ref, "autor_ref": "u_abc", "nota_comida": 5, "nota_ambiente": 4,
             "nota_atendimento": 3, "comentario": "Muito bom", "validada": True}
    assert c.post("/avaliacoes", json=corpo).status_code == 401                    # exige chave
    assert c.post("/avaliacoes", json={**corpo, "nota_comida": 6}, headers=H).status_code == 422   # nota 1..5
    r = c.post("/avaliacoes", json=corpo, headers=H)
    assert r.status_code == 201 and r.json()["status"] == "publicada"
    assert c.post("/avaliacoes", json=corpo, headers=H).status_code == 409         # uma nota fiscal = uma avaliação
    pend = c.post("/avaliacoes", json={**corpo, "experiencia_ref": ref + "-2", "validada": False}, headers=H).json()
    assert pend["status"] == "pendente"                                            # sem validação não aparece
    j = c.get(f"/lugares/{lid}/avaliacoes").json()
    assert j["resumo"]["total"] == 1 and j["resumo"]["nota"] == 4.0 and j["resumo"]["comida"] == 5.0
    assert j["resumo"]["distribuicao"]["4"] == 1 and j["itens"][0]["comentario"] == "Muito bom"
    assert "autor_ref" not in j["itens"][0]                                        # nada que identifique o autor
    assert c.patch(f"/avaliacoes/{pend['id']}", params={"status": "publicada"}, headers=H).json()["status"] == "publicada"
    assert c.get(f"/lugares/{lid}/avaliacoes").json()["resumo"]["total"] == 2


def test_health_conta_tudo():
    j = c.get("/health").json()
    assert {"lugares", "eventos", "cardapios", "imagens", "avaliacoes"} <= set(j)
