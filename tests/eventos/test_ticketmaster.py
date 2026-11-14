"""Conector Ticketmaster com respostas SIMULADAS (httpx.MockTransport). Nenhum destes testes valida a API real:
a validação real só ocorre com TICKETMASTER_API_KEY (veja `coletar_eventos.py validar-ticketmaster`)."""
import json
import httpx
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from app.models import Evento
from app.eventos.conectores import ticketmaster as tm
from app.eventos.conectores.base import (Contexto, CredencialInvalida, ErroFonte, Estatisticas, FonteBloqueada, LimiteExcedido, Requisitor, SemCredencial, redigir)
from app.eventos.persistir import ingerir

CHAVE = "CHAVE-SECRETA-DE-TESTE-123"
AGORA = datetime(2026, 11, 14, tzinfo=timezone.utc)


def evento(i="E1", nome="Show Simulado", status="onsale", data="2026-12-05T22:00:00Z", **kw):
    e = {"id": i, "name": nome, "url": f"https://www.ticketmaster.com.br/event/{i}",
         "images": [{"url": "https://s1.ticketm.net/a.jpg", "width": 1024, "height": 576, "ratio": "16_9", "fallback": False},
                    {"url": "https://s1.ticketm.net/f.jpg", "width": 100, "height": 100, "fallback": True}],
         "dates": {"start": {"dateTime": data, "localDate": data[:10]}, "timezone": "America/Sao_Paulo", "status": {"code": status}},
         "classifications": [{"segment": {"name": "Music"}, "genre": {"name": "Rock"}}],
         "priceRanges": [{"type": "standard", "currency": "BRL", "min": 80, "max": 250}],
         "promoter": {"id": "9", "name": "Produtora Simulada"},
         "_embedded": {"venues": [{"id": "V1", "name": "Casa Simulada", "city": {"name": "São Paulo"}, "state": {"stateCode": "SP"}, "country": {"countryCode": "BR"},
                                   "address": {"line1": "Rua X, 1"}, "location": {"latitude": "-23.55", "longitude": "-46.63"}}],
                       "attractions": [{"id": "A1", "name": "Banda Simulada"}]}}
    e.update(kw)
    return e


def pagina(eventos, total=None, paginas=1, n=0):
    return {"_embedded": {"events": eventos}, "page": {"size": 200, "totalElements": total if total is not None else len(eventos), "totalPages": paginas, "number": n}}


def ctx(handler, monkeypatch, config=None, limite=None):
    monkeypatch.setenv("TICKETMASTER_API_KEY", CHAVE)
    st = Estatisticas()
    cli = httpx.Client(transport=httpx.MockTransport(handler))
    req = Requisitor(client=cli, intervalo=0, espera_base=0, espera_max=0, stats=st)
    return Contexto(slug="ticketmaster", config=config or {"consultas": [{"nome": "br", "countryCode": "BR"}]}, requisitor=req, stats=st, agora=AGORA, limite=limite)


def coletar(c):
    return list(tm.Ticketmaster().coletar(c))


def test_chave_ausente_nao_chama_a_rede(monkeypatch):
    monkeypatch.delenv("TICKETMASTER_API_KEY", raising=False)
    def h(r): raise AssertionError("não deveria chamar a rede")
    c = Contexto(slug="t", config={}, requisitor=Requisitor(client=httpx.Client(transport=httpx.MockTransport(h))), stats=Estatisticas(), agora=AGORA)
    with pytest.raises(SemCredencial) as e:
        coletar(c)
    assert e.value.status == "aguardando_credencial"
    assert tm.validar_credencial({})["status"] == "aguardando_credencial"


def test_chave_invalida_401(monkeypatch):
    c = ctx(lambda r: httpx.Response(401, json={"fault": {"faultstring": "Invalid ApiKey"}}), monkeypatch)
    with pytest.raises(CredencialInvalida):
        coletar(c)


def test_consulta_usa_apikey_pais_e_parametros_documentados(monkeypatch):
    vistos = []
    def h(r):
        vistos.append(dict(r.url.params)); return httpx.Response(200, json=pagina([evento()]))
    out = coletar(ctx(h, monkeypatch))
    p = vistos[0]
    assert p["apikey"] == CHAVE and p["countryCode"] == "BR" and p["sort"] == "date,asc" and "startDateTime" in p
    assert set(p) - {"apikey"} <= tm.PARAMS_DOCUMENTADOS
    assert len(out) == 1 and out[0].fonte == "ticketmaster"


def test_busca_por_cidade_e_geopoint(monkeypatch):
    vistos = []
    def h(r):
        vistos.append(dict(r.url.params)); return httpx.Response(200, json=pagina([]))
    cfg = {"consultas": [{"nome": "sp", "countryCode": "BR", "city": "São Paulo"}, {"nome": "r", "geoPoint": "6gyf4bf", "radius": 50, "unit": "km"}]}
    coletar(ctx(h, monkeypatch, cfg))
    assert vistos[0]["city"] == "São Paulo" and vistos[1]["geoPoint"] == "6gyf4bf" and "latlong" not in vistos[1]


def test_params_nao_documentados_sao_recusados():
    with pytest.raises(ValueError):
        tm.validar_params({"countryCode": "BR", "artistName": "x"})
    with pytest.raises(ValueError):
        tm.validar_params({"source": "stubhub"})


def test_busca_por_data(monkeypatch):
    vistos = []
    def h(r):
        vistos.append(dict(r.url.params)); return httpx.Response(200, json=pagina([]))
    coletar(ctx(h, monkeypatch, {"dias_a_frente": 30, "consultas": [{"nome": "x", "countryCode": "BR"}]}))
    assert vistos[0]["startDateTime"] == "2026-11-14T00:00:00Z" and vistos[0]["endDateTime"] == "2026-12-14T00:00:00Z"


def test_paginacao(monkeypatch):
    def h(r):
        n = int(r.url.params["page"])
        return httpx.Response(200, json=pagina([evento(f"E{n}{k}") for k in range(2)], total=6, paginas=3, n=n))
    out = coletar(ctx(h, monkeypatch, {"tamanho_pagina": 2, "consultas": [{"nome": "x", "countryCode": "BR"}]}))
    assert len(out) == 6


def test_limite_de_paginacao_profunda_divide_janela(monkeypatch):
    chamadas = []
    def h(r):
        p = dict(r.url.params); chamadas.append(p)
        ini, fim = p["startDateTime"], p["endDateTime"]
        grande = (datetime.strptime(fim, "%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(ini, "%Y-%m-%dT%H:%M:%SZ")).days > 200
        if grande:
            return httpx.Response(200, json=pagina([], total=1500, paginas=8))
        return httpx.Response(200, json=pagina([evento("A" + ini)], total=1))
    out = coletar(ctx(h, monkeypatch, {"consultas": [{"nome": "x", "countryCode": "BR"}]}))
    assert len(chamadas) > 1 and len(out) >= 1


def test_normalizacao_imagens_precos_status_e_campos(monkeypatch):
    b = tm.normalizar_evento(evento())
    assert b.preco_min == 80 and b.preco_max == 250 and b.moeda == "BRL"
    assert any(i.fallback for i in b.imagens) and any(not i.fallback for i in b.imagens)
    assert b.local.nome == "Casa Simulada" and b.local.lat == -23.55 and b.local.pais == "BR"
    assert b.artistas[0].nome == "Banda Simulada" and b.organizador.nome == "Produtora Simulada"
    assert "Rock" in b.categorias and b.plataforma == "ticketmaster" and b.ingresso_url.startswith("https://")
    assert tm.plataforma_da_url("https://www.universe.com/events/x") == "universe"
    assert tm.normalizar_evento({"id": "x"}) is None


def test_evento_sem_preco_nao_inventa_valor():
    e = evento(); e.pop("priceRanges")
    b = tm.normalizar_evento(e)
    assert b.preco_min is None and b.preco_max is None and b.gratuito is None


def test_cancelado_e_remarcado_viram_status(monkeypatch, db):
    ingerir(db, "tm", [tm.normalizar_evento(evento(status="onsale"), "tm")])
    ingerir(db, "tm", [tm.normalizar_evento(evento(status="cancelled"), "tm")])
    assert db.scalars(select(Evento)).one().status == "cancelado"


def test_evento_vencido_nao_aparece_como_futuro(db):
    from app.eventos.persistir import ciclo_de_vida
    ingerir(db, "tm", [tm.normalizar_evento(evento(data="2020-01-01T22:00:00Z"), "tm")])
    ciclo_de_vida(db)
    assert db.scalars(select(Evento)).one().status == "encerrado"


def test_data_a_definir_nao_inventa_data():
    e = evento(); e["dates"] = {"start": {"dateTBD": True}, "status": {"code": "onsale"}}
    b = tm.normalizar_evento(e)
    assert b.inicio is None and b.data_incerta is True


def test_429_tenta_de_novo_e_depois_desiste(monkeypatch):
    n = {"c": 0}
    def h(r):
        n["c"] += 1
        return httpx.Response(429, headers={"retry-after": "0"}) if n["c"] < 3 else httpx.Response(200, json=pagina([evento()]))
    assert len(coletar(ctx(h, monkeypatch))) == 1 and n["c"] == 3
    with pytest.raises(LimiteExcedido):
        coletar(ctx(lambda r: httpx.Response(429, headers={"retry-after": "0"}), monkeypatch))


def test_5xx_retentativas_e_fonte_fora_do_ar(monkeypatch):
    with pytest.raises(ErroFonte) as e:
        coletar(ctx(lambda r: httpx.Response(503), monkeypatch))
    assert CHAVE not in str(e.value)
    def cai(r): raise httpx.ConnectError("sem rede " + str(r.url))
    with pytest.raises(ErroFonte) as e2:
        coletar(ctx(cai, monkeypatch))
    assert CHAVE not in str(e2.value)


def test_chave_nunca_aparece_em_erros(monkeypatch):
    def cai(r): raise httpx.ConnectError(f"falha em {r.url}")
    try:
        coletar(ctx(cai, monkeypatch))
    except ErroFonte as e:
        assert CHAVE not in str(e) and "apikey=***" in redigir(f"https://x?apikey={CHAVE}&a=1")
    assert CHAVE not in redigir(f"erro {CHAVE}", (CHAVE,))


def test_403_vira_fonte_bloqueada(monkeypatch):
    with pytest.raises(FonteBloqueada):
        coletar(ctx(lambda r: httpx.Response(403), monkeypatch))


def test_protecao_da_quota(monkeypatch):
    def h(r):
        n = int(r.url.params["page"])
        return httpx.Response(200, json=pagina([evento(f"Q{n}")], total=5, paginas=5, n=n), headers={"Rate-Limit-Available": "10"})
    c = ctx(h, monkeypatch, {"tamanho_pagina": 1, "quota_minima": 100, "consultas": [{"nome": "x", "countryCode": "BR"}]})
    out = coletar(c)
    assert len(out) == 1 and c.stats.parcial


def test_validar_credencial_simulado(monkeypatch):
    monkeypatch.setenv("TICKETMASTER_API_KEY", CHAVE)
    cli = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=pagina([], total=7))))
    r = tm.validar_credencial({}, cli)
    assert r["ok"] and r["eventos_brasil"] == 7 and CHAVE not in json.dumps(r)
    cli2 = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401)))
    assert tm.validar_credencial({}, cli2)["status"] == "chave_invalida"


def test_disponibilidade_brasil_com_dados_simulados(db, monkeypatch):
    """Garante que o pipeline aceita, grava e consulta eventos fora de SP capital (Brasil inteiro). Dados SIMULADOS."""
    def h(r):
        return httpx.Response(200, json=pagina([evento("S1"), evento("R1", "Show Rio", **{"_embedded": {"venues": [{"id": "V2", "name": "Arena Rio", "city": {"name": "Rio de Janeiro"}, "state": {"stateCode": "RJ"}, "country": {"countryCode": "BR"}}]}}),
                                                evento("I1", "Show Lisboa", **{"_embedded": {"venues": [{"id": "V3", "name": "Sala Lisboa", "city": {"name": "Lisboa"}, "country": {"countryCode": "PT"}}]}})]))
    brutos = coletar(ctx(h, monkeypatch))
    ingerir(db, "ticketmaster", brutos)
    from app.eventos.modelos import EventoLocal
    cidades = {l.cidade for l in db.scalars(select(EventoLocal))}
    assert len(db.scalars(select(Evento)).all()) == 3
    assert {"São Paulo", "Rio de Janeiro", "Lisboa"} <= cidades


def test_protecao_da_chave_em_logs_banco_snapshot_e_arquivos(db, monkeypatch, tmp_path):
    """A chave (valor de teste) não pode aparecer em: log de coleta, saúde da fonte, histórico, snapshot, API pública e arquivos versionados."""
    import gzip, subprocess
    from app.eventos.agendador import executar_fonte
    from app.eventos.modelos import EventoColetaLog, EventoFonte
    from app.eventos import snapshot
    monkeypatch.setenv("TICKETMASTER_API_KEY", CHAVE)
    def h(r):
        if int(r.url.params.get("page", 0)) == 0 and r.url.params.get("city"):
            raise httpx.ConnectError(f"falha em {r.url}")           # mensagem de erro carregando a URL com ?apikey=...
        return httpx.Response(200, json=pagina([evento("K1")]))
    f = EventoFonte(slug="tmk", nome="tm", conector="ticketmaster", config={"consultas": [{"nome": "br", "countryCode": "BR"}, {"nome": "sp", "countryCode": "BR", "city": "São Paulo"}]})
    db.add(f); db.commit()
    cli = httpx.Client(transport=httpx.MockTransport(h))
    st = Estatisticas()
    req = Requisitor(client=cli, intervalo=0, espera_base=0, espera_max=0, stats=st)
    log = executar_fonte(db, f, requisitor=req)
    assert log.status == "erro" and CHAVE not in log.mensagem and CHAVE not in (f.ultimo_erro or "")
    snapshot.exportar(db, str(tmp_path))
    assert CHAVE.encode() not in gzip.open(tmp_path / snapshot.ARQUIVO).read()
    from sqlalchemy import select as sel
    assert all(CHAVE not in (l.mensagem or "") for l in db.scalars(sel(EventoColetaLog)))
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    for rota in ("/eventos", "/eventos/categorias", "/health"):
        assert CHAVE not in c.get(rota).text
    arquivos = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split()
    for a in arquivos:
        if a.endswith((".png", ".jpg", ".gz", ".ico")) or a.startswith("tests/"):   # os testes citam a chave de teste de propósito
            continue
        try:
            assert CHAVE not in open(a, encoding="utf-8", errors="ignore").read(), a
        except IsADirectoryError:
            pass


def test_nenhum_segredo_versionado():
    """.env.example não traz valores; nenhum arquivo versionado tem 'apikey=<valor longo>'."""
    import re, subprocess
    env = open(".env.example", encoding="utf-8").read()
    m = re.search(r"^TICKETMASTER_API_KEY=(.*)$", env, re.M)
    assert m and m.group(1).split("#")[0].strip() == ""
    suspeito = re.compile(r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?[A-Za-z0-9]{24,}")
    for a in subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split():
        if a.endswith((".png", ".jpg", ".gz", ".ico", ".html")) or a.startswith("tests/"):
            continue
        assert not suspeito.search(open(a, encoding="utf-8", errors="ignore").read()), a
