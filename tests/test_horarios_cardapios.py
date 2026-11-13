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
