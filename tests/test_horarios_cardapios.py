import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
from datetime import datetime
from sqlalchemy import select
from app.db import Base, SessionLocal, engine
from app.ingest import upsert
from app.models import Cardapio, Lugar
from app.sources import cardapios, horarios
from app.sources.horarios import TZ


def em(dia, hh, mm=0):
    """2026-11-02 é segunda-feira."""
    return datetime(2026, 11, 2 + dia, hh, mm, tzinfo=TZ)


def test_horario_simples_e_faixas():
    h = horarios.parse("Mo-Fr 11:30-15:00,18:00-23:00; Sa 12:00-23:00; Su off")
    assert h["dias"]["seg"] == [["11:30", "15:00"], ["18:00", "23:00"]]
    assert h["dias"]["sab"] == [["12:00", "23:00"]] and h["dias"]["dom"] == []
    assert horarios.aberto_agora(h, em(0, 12)) is True      # segunda 12:00
    assert horarios.aberto_agora(h, em(0, 16)) is False     # intervalo da tarde
    assert horarios.aberto_agora(h, em(6, 13)) is False     # domingo fechado


def test_horario_vira_a_noite_e_24h():
    h = horarios.parse("Mo-Su 18:00-02:00")
    assert horarios.aberto_agora(h, em(0, 23)) is True       # segunda 23:00
    assert horarios.aberto_agora(h, em(1, 1)) is True        # terça 01:00 ainda é a noite de segunda
    assert horarios.aberto_agora(h, em(1, 3)) is False
    assert horarios.aberto_agora(horarios.parse("24/7"), em(3, 4)) is True


def test_horario_sem_dias_e_feriado():
    assert horarios.parse("12:00 - 18:00")["dias"]["qua"] == [["12:00", "18:00"]]
    h = horarios.parse("Mo-Su 10:00-22:00; PH off")
    assert h["feriados"] == [] and h["dias"]["seg"] == [["10:00", "22:00"]]


def test_horario_regras_separadas_por_virgula_sem_quebrar_lista_de_dias():
    h = horarios.parse("Mo-Fr 07:00-23:00, Sa 08:00-24:00, Su 12:00-23:00")
    assert h["dias"]["sex"] == [["07:00", "23:00"]] and h["dias"]["sab"] == [["08:00", "24:00"]] and h["dias"]["dom"] == [["12:00", "23:00"]]
    h2 = horarios.parse("Mo,We 10:00-12:00")   # vírgula entre dias continua sendo lista de dias
    assert h2["dias"]["seg"] == [["10:00", "12:00"]] and h2["dias"]["qua"] == [["10:00", "12:00"]] and h2["dias"]["ter"] == []
    assert horarios.parse("Mo-Fr 11:00-14:00, 17:30-19:45")["dias"]["qui"] == [["11:00", "14:00"], ["17:30", "19:45"]]  # duas faixas, mesma regra


def test_horario_complexo_devolve_none_em_vez_de_adivinhar():
    for oh in ("Mo-Fr sunrise-sunset", "Jan-Mar Mo-Fr 10:00-12:00", "week 1-3 Mo 10:00-12:00", "", "qualquer coisa"):
        assert horarios.parse(oh) is None
    assert horarios.aberto_agora(None) is None


JSONLD = '''<script type="application/ld+json">{"@type":"Restaurant","name":"X","hasMenu":{"@type":"Menu","url":"https://x.com/menu",
 "hasMenuSection":[{"@type":"MenuSection","name":"Massas","hasMenuItem":[
   {"@type":"MenuItem","name":"Penne","description":"Ao sugo","offers":{"@type":"Offer","price":"42.50","priceCurrency":"BRL"}}]}]}}</script>'''


def test_cardapio_jsonld_confirmado_com_itens():
    r = cardapios.buscar(JSONLD, "https://x.com/")
    assert r[0]["origem"] == "jsonld" and r[0]["status"] == "confirmado" and r[0]["url"] == "https://x.com/menu"
    assert r[0]["itens"] == [{"secao": "Massas", "nome": "Penne", "descricao": "Ao sugo", "preco": 42.5}]


def test_cardapio_links_plataformas_pdf_e_proprio():
    html = '''<nav><a href="#">Menu</a><a href="javascript:void(0)">Menu</a><a href="/contato">Contato</a>
      <a href="https://instagram.com/x">Cardápio no Instagram</a>
      <a href="https://app.goomer.app/menu/abc">Pedir</a>
      <a href="/wp-content/cardapio-2026.pdf">Cardápio (PDF)</a>
      <a href="/cardapio">Ver</a></nav>'''
    r = cardapios.buscar(html, "https://bar.com.br/")
    urls = {x["url"]: x["plataforma"] for x in r}
    assert urls == {"https://app.goomer.app/menu/abc": "goomer", "https://bar.com.br/wp-content/cardapio-2026.pdf": "pdf",
                    "https://bar.com.br/cardapio": "proprio"}
    assert all(x["status"] == "provavel" and x["origem"] == "link_site" for x in r)


def test_cardapio_osm_tag_e_sem_falso_positivo():
    r = cardapios.buscar("<a href='#'>Menu</a><a href='/sobre'>Sobre</a>", "https://x.com/", menu_osm="https://x.com/carta.pdf")
    assert [(x["origem"], x["plataforma"], x["status"]) for x in r] == [("osm_tag", "pdf", "confirmado")]
    assert cardapios.buscar("<a href='#'>Menu</a><a href='/sobre'>Sobre</a>", "https://x.com/") == []


def test_cardapio_coletar_respeita_robots_e_redes(monkeypatch):
    import httpx
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /fechado")
        return httpx.Response(200, text='<a href="/cardapio">Cardápio</a>')
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    ls = [{"fonte": "osm", "fonte_id": "node/1", "site": "https://aberto.com/"},
          {"fonte": "osm", "fonte_id": "node/2", "site": "https://fechado.com/fechado"},
          {"fonte": "osm", "fonte_id": "node/3", "site": "https://instagram.com/bar"}]
    regs, st = cardapios.coletar(ls, client=client, pausa=0)
    assert [r["lugar_fonte_id"] for r in regs] == ["node/1"]
    assert st["bloqueados_robots"] == 0 or st["bloqueados_robots"] == 1
    assert st["ignorados_rede_social"] == 1 and st["com_cardapio"] == 1


def test_upsert_preserva_extra_de_outros_bots_e_cardapio_idempotente():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        base = {"fonte": "osm", "fonte_id": "node/9", "tipo": "bar", "nome": "Bar", "extra": {"nominatim": 1, "endereco_aproximado": True}}
        upsert(db, Lugar, [base])
        upsert(db, Lugar, [{**base, "extra": {"takeaway": "yes"}}])  # nova coleta do OSM não pode apagar o endereço do Nominatim
        assert db.scalar(select(Lugar).where(Lugar.fonte_id == "node/9")).extra == {"nominatim": 1, "endereco_aproximado": True, "takeaway": "yes"}
        c = {"lugar_fonte": "osm", "lugar_fonte_id": "node/9", "url": "https://x.com/cardapio", "plataforma": "proprio"}
        assert upsert(db, Cardapio, [c]) == {"novos": 1, "atualizados": 0}
        assert upsert(db, Cardapio, [c]) == {"novos": 0, "atualizados": 1}


def test_robots_distingue_proibido_de_erro():
    import httpx
    from app.sources.sites import robots
    def com(status, texto=""):
        return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, text=texto)))
    assert robots("https://a.com/x", com(404)) == "ok"                                   # sem robots.txt: livre (RFC 9309)
    assert robots("https://a.com/x", com(200, "User-agent: *\nDisallow: /")) == "proibido"
    assert robots("https://a.com/x", com(503)) == "erro"                                  # servidor com problema: não visitar
    def boom(req):
        raise httpx.ConnectTimeout("lento")
    assert robots("https://a.com/x", httpx.Client(transport=httpx.MockTransport(boom))) == "erro"


def test_listagem_segue_links_de_eventos():
    from app.sources import sites
    html = '<a href="/evento/show-1">a</a><a href="/evento/show-2?id=7&utm_source=x">b</a><a href="/sobre">c</a><a href="https://outro.com/evento/z">d</a><a href="/evento/show-1">dup</a>'
    assert sites.links_listagem(html, "https://s.com/lista", r"^/evento/") == ["https://s.com/evento/show-1", "https://s.com/evento/show-2?id=7"]
    assert sites.links_listagem(html, "https://s.com/lista", r"^/evento/", limite=1) == ["https://s.com/evento/show-1"]


def test_filtro_de_cidade_e_obter_com_retry(monkeypatch):
    import httpx
    from app.sources import sites
    sp = {"endereco": "Rua A, 1, São Paulo", "lat": None, "lon": None}
    assert sites.da_cidade(sp, "São Paulo") and sites.da_cidade(sp, "sao paulo")
    assert not sites.da_cidade({"endereco": "Av. B, Rio de Janeiro"}, "São Paulo")
    assert sites.da_cidade({"endereco": "", "lat": -23.55, "lon": -46.63}, "São Paulo")
    assert not sites.da_cidade({"endereco": "", "lat": -22.9, "lon": -43.2}, "São Paulo")   # Rio pelas coordenadas
    assert not sites.da_cidade({"endereco": "", "lat": None, "lon": None}, "São Paulo")      # sem informação: não arrisca
    assert sites.da_cidade({"endereco": "qualquer"}, "")                                      # sem filtro: aceita tudo
    chamadas = []
    def h(req):
        chamadas.append(1)
        return httpx.Response(429, headers={"retry-after": "1"}) if len(chamadas) == 1 else httpx.Response(200, text="ok")
    monkeypatch.setattr(sites.time, "sleep", lambda s: None)
    r = sites.obter(httpx.Client(transport=httpx.MockTransport(h)), "https://x.com/")
    assert r.status_code == 200 and len(chamadas) == 2


def test_coletar_sites_respeita_ativo_cidade_e_listagem(tmp_path, monkeypatch):
    import httpx
    from app.sources import sites
    monkeypatch.setattr(sites.time, "sleep", lambda s: None)
    ev = lambda nome, cid: ('<script type="application/ld+json">{"@type":"Event","name":"%s","startDate":"2026-12-01T20:00:00-03:00",'
                            '"location":{"name":"L","address":{"streetAddress":"Rua 1","addressLocality":"%s"}}}</script>' % (nome, cid))
    def h(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        if req.url.path == "/lista":
            return httpx.Response(200, text='<a href="/evento/a">A</a><a href="/evento/b">B</a>')
        return httpx.Response(200, text=ev("Evento SP" if req.url.path.endswith("a") else "Evento Rio", "São Paulo" if req.url.path.endswith("a") else "Rio de Janeiro"))
    cfg = tmp_path / "s.yml"
    cfg.write_text("sites:\n  - {url: 'https://s.com/lista', listagem: true, padrao_link: '^/evento/', cidade: 'São Paulo'}\n"
                   "  - {url: 'https://off.com/lista', listagem: true, padrao_link: '^/evento/', ativo: false}\n")
    l, e, ign = sites.coletar(str(cfg), client=httpx.Client(transport=httpx.MockTransport(h), follow_redirects=True), pausa=0)
    assert [x["titulo"] for x in e] == ["Evento SP"] and ign == []      # Rio filtrado, site desativado nem visitado


def test_uma_fonte_com_erro_nao_derruba_as_outras(tmp_path, monkeypatch):
    import httpx
    from app.sources import sites
    monkeypatch.setattr(sites.time, "sleep", lambda s: None)
    ev = '<script type="application/ld+json">{"@type":"Event","name":"Bom","startDate":"2026-12-01T20:00:00-03:00"}</script>'
    def h(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        return httpx.Response(429) if req.url.host == "ruim.com" else httpx.Response(200, text=ev)
    cfg = tmp_path / "s.yml"
    cfg.write_text("sites:\n  - {url: 'https://ruim.com/agenda'}\n  - {url: 'https://bom.com/agenda'}\n")
    l, e, ign = sites.coletar(str(cfg), client=httpx.Client(transport=httpx.MockTransport(h), follow_redirects=True), pausa=0)
    assert [x["titulo"] for x in e] == ["Bom"]                    # o bom foi coletado
    assert any("ruim.com" in i and "erro" in i for i in ign)      # o ruim ficou registrado como erro
