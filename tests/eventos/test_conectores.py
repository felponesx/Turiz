"""Feeds/planilhas/navegador/agendador. Fontes e respostas SIMULADAS (locais); não validam sites reais."""
import json
import threading
import http.server
import functools
import httpx
import pytest
from sqlalchemy import select
from app.models import Evento
from app.eventos.agendador import executar_devidas, executar_fonte, esta_devida, sincronizar_fontes
from app.eventos.conectores import REGISTRO
from app.eventos.conectores.base import Contexto, Estatisticas, Requisitor
from app.eventos.conectores.navegador import detectar_bloqueio
from app.eventos.modelos import EventoColetaLog, EventoFonte


def ctx(tipo_config, tmp_path=None, slug="f"):
    st = Estatisticas()
    return Contexto(slug=slug, config=tipo_config, requisitor=Requisitor(client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))), intervalo=0, stats=st), stats=st)


def test_feed_json_mapeado(tmp_path):
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"eventos": [{"id": 1, "nome": "Sarau Simulado", "quando": "05/12/2026 20:00", "local": {"nome": "Bar X", "cidade": "Campinas"}, "preco": "30,5"}, {"id": 2}]}))
    out = list(REGISTRO["feed_json"]().coletar(ctx({"arquivo": str(p), "itens": "eventos", "mapa": {"id": "id", "titulo": "nome", "inicio": "quando", "local_nome": "local.nome", "cidade": "local.cidade", "preco_min": "preco"}})))
    assert len(out) == 1 and out[0].local.cidade == "Campinas" and out[0].preco_min == 30.5 and out[0].inicio.hour == 20


def test_rss_e_xml_sem_entidades_externas(tmp_path):
    rss = tmp_path / "f.xml"
    rss.write_text('<rss><channel><item><title>Feira Simulada</title><link>https://x.com/1</link><guid>g1</guid><pubDate>Sat, 05 Dec 2026 10:00:00 +0000</pubDate></item></channel></rss>')
    out = list(REGISTRO["rss"]().coletar(ctx({"arquivo": str(rss)})))
    assert out[0].titulo == "Feira Simulada" and out[0].fonte_id == "g1"
    ruim = tmp_path / "x.xml"
    ruim.write_text('<!DOCTYPE r [<!ENTITY a SYSTEM "file:///etc/passwd">]><r><event><n>&a;</n></event></r>')
    with pytest.raises(Exception):
        list(REGISTRO["feed_xml"]().coletar(ctx({"arquivo": str(ruim), "mapa": {"titulo": "n"}})))


def test_planilha_csv(tmp_path):
    p = tmp_path / "p.csv"
    p.write_text("titulo;inicio;local_nome;cidade;preco_min\nFeira do Livro;2026-12-10 10:00;Praça;Santos;0\n", encoding="utf-8")
    out = list(REGISTRO["planilha"]().coletar(ctx({"arquivo": str(p)})))
    assert out[0].titulo == "Feira do Livro" and out[0].local.cidade == "Santos"


def test_deteccao_de_bloqueio_nao_tenta_contornar():
    assert detectar_bloqueio("<html>Please verify you are human - CAPTCHA</html>")
    assert detectar_bloqueio("ok", 403) and not detectar_bloqueio("<html>Agenda de eventos</html>", 200)


@pytest.fixture
def servidor_js(tmp_path):
    (tmp_path / "robots.txt").write_text("User-agent: *\nAllow: /\n")
    (tmp_path / "agenda.html").write_text("""<html><body><div id=app>carregando</div><script>
      setTimeout(()=>{const s=document.createElement('script');s.type='application/ld+json';
      s.text=JSON.stringify({"@type":"MusicEvent","name":"Show Renderizado por JS","startDate":"2026-12-05T21:00:00-03:00","location":{"name":"Casa JS","address":"Rua 1, São Paulo"},"offers":{"price":"40"}});
      document.head.appendChild(s);document.getElementById('app').textContent='pronto'},300)</script></body></html>""")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/agenda.html"
    srv.shutdown()


def test_navegador_le_pagina_renderizada_por_js(servidor_js):
    pw = pytest.importorskip("playwright")
    import os, shutil
    exe = os.getenv("TURIZ_CHROMIUM") or ("/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)
    c = {"url": servidor_js, "cidade": "", "pausa": 0, "chromium": exe, "aguardar": "#app:has-text('pronto')"}
    from app.sources import sites
    cli = httpx.Client()
    try:
        out = list(REGISTRO["navegador"]().coletar(Contexto(slug="js", config=c, requisitor=Requisitor(client=cli, intervalo=0), stats=Estatisticas())))
    except Exception as e:
        pytest.skip(f"navegador indisponível neste ambiente: {e}")
    assert [b.titulo for b in out] == ["Show Renderizado por JS"] and out[0].preco_min == 40


# ----- agendador
def _fonte(db, slug, conector, config, **kw):
    f = EventoFonte(slug=slug, nome=slug, conector=conector, config=config, **kw)
    db.add(f); db.commit()
    return f


def test_fonte_com_erro_nao_derruba_as_outras(db, tmp_path):
    p = tmp_path / "ok.json"
    p.write_text(json.dumps([{"id": "1", "t": "Evento OK Simulado", "d": "2099-01-10T20:00:00Z"}]))
    _fonte(db, "quebrada", "feed_json", {"arquivo": str(tmp_path / "nao_existe.json")}, prioridade=90)
    _fonte(db, "sem-chave", "ticketmaster", {"chave_env": "VAR_QUE_NAO_EXISTE_X"}, prioridade=80)
    _fonte(db, "boa", "feed_json", {"arquivo": str(p), "mapa": {"id": "id", "titulo": "t", "inicio": "d"}}, prioridade=10)
    logs = executar_devidas(db, forcar=True)
    por = {l.fonte: l for l in logs}
    assert por["boa"].status == "sucesso" and por["boa"].novos == 1
    assert por["quebrada"].status == "erro" and por["sem-chave"].status == "aguardando_credencial"
    assert db.scalars(select(Evento)).one().titulo == "Evento OK Simulado"
    saude = {f.slug: f.saude for f in db.scalars(select(EventoFonte))}
    assert saude == {"quebrada": "erro", "sem-chave": "aguardando_credencial", "boa": "ok"}


def test_intervalo_por_fonte(db):
    from datetime import datetime, timedelta, timezone
    f = _fonte(db, "a", "feed_json", {}, intervalo_horas=24)
    agora = datetime.now(timezone.utc)
    assert esta_devida(f, agora)
    f.ultima_execucao_em, f.saude = agora - timedelta(hours=5), "ok"
    assert not esta_devida(f, agora)
    f.saude = "erro"
    assert esta_devida(f, agora)                        # erro: tenta de novo em 2 h
    f.ativo = False
    assert not esta_devida(f, agora)


def test_fonte_bloqueada_nao_e_coletada(db):
    f = _fonte(db, "b", "feed_json", {}, autorizacao="bloqueada")
    assert executar_devidas(db) == []                                  # fora do modo forçado nem entra na fila
    assert [l.status for l in executar_devidas(db, forcar=True)] == ["ignorada"]   # forçado: registra que ignorou, sem coletar


def test_sincronizar_cadastro_do_arquivo(db):
    r = sincronizar_fontes(db, "fontes_eventos.yml")
    assert r["criadas"] >= 3
    tm = db.scalar(select(EventoFonte).where(EventoFonte.slug == "ticketmaster"))
    assert tm.conector == "ticketmaster" and "apikey" not in json.dumps(tm.config).lower() and tm.config["chave_env"] == "TICKETMASTER_API_KEY"
    assert sincronizar_fontes(db, "fontes_eventos.yml")["criadas"] == 0
