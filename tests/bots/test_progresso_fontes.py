import httpx

from app.sources import imagens, osm, instagram
from bots.status import Reporter


def test_osm_reporta_progresso_por_regiao(tmp_path, monkeypatch):
    monkeypatch.setattr(osm.time, "sleep", lambda s: None)
    r = Reporter("osm", pasta=str(tmp_path))
    r.iniciar()
    el = {"type": "node", "id": 1, "lat": -23.5, "lon": -46.6, "tags": {"name": "Bar Um", "amenity": "bar"}}
    regs = osm.coletar(linhas=2, colunas=2, post=lambda q: {"elements": [el]}, progresso=r.callback())
    assert len(regs) == 1                                   # o mesmo lugar nas 4 regiões vira 1
    assert r.percentual == 99 and r.feitos == 4 and r.total == 4
    assert r.contagem["captados"] == 1                      # só a primeira região viu o lugar pela 1ª vez
    assert r.itens[0]["txt"] == "Bar Um"


def _cliente(corpo, status=200):
    def h(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(status, text=corpo)
    return httpx.Client(transport=httpx.MockTransport(h), follow_redirects=True)


def test_imagens_sites_reporta_bloqueios_e_achados(tmp_path, monkeypatch):
    monkeypatch.setattr(imagens.time, "sleep", lambda s: None)
    r = Reporter("imagens", pasta=str(tmp_path))
    r.iniciar()
    lugares = [{"fonte": "osm", "fonte_id": "node/1", "site": "https://a.com"}, {"fonte": "osm", "fonte_id": "node/2", "site": "https://b.com"}]
    regs, st = imagens.coletar_sites(lugares, client=_cliente('<meta property="og:image" content="https://a.com/x.jpg">'), progresso=r.callback())
    assert len(regs) == 2 and r.contagem["captados"] == 2 and r.percentual == 99
    assert r.atual == "b.com"


def test_redes_reporta_perfis_encontrados(tmp_path, monkeypatch):
    monkeypatch.setattr(instagram.time, "sleep", lambda s: None)
    r = Reporter("instagram", pasta=str(tmp_path))
    r.iniciar()
    lugares = [{"fonte": "osm", "fonte_id": "node/1", "site": "https://a.com"}]
    regs, st = instagram.vinculos_sites(lugares, client=_cliente('<a href="https://instagram.com/bar_a/">ig</a>'), progresso=r.callback())
    assert regs[0]["usuario"] == "bar_a" and r.itens[0]["txt"] == "a.com: @bar_a"
