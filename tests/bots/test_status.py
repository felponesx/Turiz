import base64
import json
import os
import sys

import httpx
import pytest

from bots import registry, status
from bots.status import Reporter, bot, redigir

# chave FALSA, só para testar a redação (nunca coloque chaves reais em testes)
CHAVE_FALSA = "AIza" + "X" * 35
TOKEN_FALSO = "ghp_" + "y" * 30


def test_redigir_esconde_segredos():
    t = redigir(f"chave {CHAVE_FALSA} e {TOKEN_FALSO} api_key=abc123 foo@bar.com")
    assert "AIza" not in t and "ghp_" not in t and "abc123" not in t and "@" not in t


def test_percentual_monotono_e_faixas(tmp_path):
    r = Reporter("osm", pasta=str(tmp_path))
    r.iniciar()
    with r.faixa(0, 50):
        r.progresso(5, 10)
    assert r.percentual == 25
    with r.faixa(50, 100):
        r.progresso(1, 10)
    assert r.percentual == 55
    r.progresso(0, 10)  # nunca volta para trás
    assert r.percentual >= 55
    r.progresso(10, 10)
    assert r.percentual == 99  # 100 só ao finalizar
    r.finalizar("concluido")
    assert r.percentual == 100 and r.estado == "concluido"
    arq = json.load(open(tmp_path / "osm.json", encoding="utf-8"))
    assert arq["estado"] == "concluido" and arq["historico"][0]["estado"] == "concluido"


def test_itens_log_avisos_limitados_e_redigidos(tmp_path):
    r = Reporter("osm", pasta=str(tmp_path))
    r.iniciar()
    for i in range(100):
        r.item(f"Lugar {i}")
        r.log(f"linha {i} token=segredo{i}")
    assert len(r.itens) == status.MAX_ITENS and r.itens[0]["txt"] == "Lugar 99"
    assert len(r.log_) <= status.MAX_LOG and all("segredo" not in x["txt"] for x in r.log_)
    r.aviso("falha numa fonte")
    r.finalizar("concluido")
    assert r.estado == "avisos"   # concluído com avisos


def test_contexto_erro_e_pular(tmp_path):
    with pytest.raises(ValueError):
        with bot("osm", publicador=None, pasta=str(tmp_path)):
            raise ValueError("quebrou")
    assert json.load(open(tmp_path / "osm.json"))["estado"] == "erro"
    with bot("google", publicador=None, pasta=str(tmp_path)):   # não propaga: job continua verde
        status.aguardar_credencial("GOOGLE_PLACES_API_KEY")
    d = json.load(open(tmp_path / "google.json"))
    assert d["estado"] == "aguardando_credencial" and "GOOGLE_PLACES_API_KEY" in d["mensagem"]


def test_tee_captura_prints_sem_vazar(tmp_path, capsys):
    with bot("osm", publicador=None, pasta=str(tmp_path)) as r:
        print("consultados: 10 token=xyz")
    assert any("consultados: 10" in x["txt"] and "xyz" not in x["txt"] for x in r.log_)
    assert "consultados: 10" in capsys.readouterr().out   # a saída normal continua aparecendo


def test_system_exit_zero_conta_como_sucesso(tmp_path):
    with bot("fotos", publicador=None, pasta=str(tmp_path)):
        sys.exit(0)
    assert json.load(open(tmp_path / "fotos.json"))["estado"] == "concluido"


def test_publicador_cria_branch_orfao_e_grava(tmp_path):
    chamadas, arquivos, criado = [], {}, []

    def handler(req):
        m, p = req.method, req.url.path
        chamadas.append((m, p))
        if p.endswith("/git/ref/heads/bot-status"):
            return httpx.Response(200 if criado else 404, json={})
        if p.endswith("/git/trees"):
            return httpx.Response(201, json={"sha": "t1"})
        if p.endswith("/git/commits"):
            assert json.loads(req.content)["parents"] == []   # órfão: sem o código nem os dados
            return httpx.Response(201, json={"sha": "c1"})
        if p.endswith("/git/refs"):
            criado.append(1)
            return httpx.Response(201, json={})
        if "/contents/" in p and m == "GET":
            return httpx.Response(404)
        if "/contents/" in p and m == "PUT":
            corpo = json.loads(req.content)
            assert corpo["branch"] == "bot-status"
            arquivos[p] = json.loads(base64.b64decode(corpo["content"]))
            return httpx.Response(201, json={"content": {"sha": "s1"}})
        return httpx.Response(500)
    pub = status.Publicador("o/r", "tok", client=httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler)))
    r = Reporter("osm", pub, pasta=str(tmp_path))
    r.iniciar()
    r.progresso(1, 4, atual="Região 1/4")
    r.finalizar("concluido")
    assert arquivos["/repos/o/r/contents/status/osm.json"]["estado"] == "concluido"
    assert ("POST", "/repos/o/r/git/refs") in chamadas


def test_falha_de_publicacao_nao_derruba_o_bot(tmp_path):
    pub = status.Publicador("o/r", "tok", client=httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    with bot("osm", publicador=pub, pasta=str(tmp_path)) as r:
        r.progresso(1, 2)
    assert json.load(open(tmp_path / "osm.json"))["estado"] == "concluido"


def test_nao_publica_sem_optin(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("TURIZ_STATUS_PUBLICAR", raising=False)
    assert status.criar_publicador() is None
    monkeypatch.setenv("TURIZ_STATUS_PUBLICAR", "1")
    assert status.criar_publicador() is not None


def test_registro_consistente_e_painel_em_dia():
    ids = [b["id"] for b in registry.BOTS]
    assert len(ids) == len(set(ids))
    assert all(b["grupo"] in registry.GRUPOS for b in registry.BOTS)
    p = os.path.join(os.path.dirname(__file__), "..", "..", "painel", "bots.json")
    if os.path.exists(p):
        assert json.load(open(p, encoding="utf-8")) == json.loads(registry.como_json()), "rode: python -m bots.registry > painel/bots.json"
    pj = os.path.join(os.path.dirname(__file__), "..", "..", "painel", "bots.js")
    if os.path.exists(pj):
        assert open(pj, encoding="utf-8").read() == registry.como_js(), "rode: python -m bots.registry --js > painel/bots.js"


def test_cli_inicio_progresso_fim(tmp_path, monkeypatch):
    from bots import cli
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TURIZ_STATUS_PUBLICAR", raising=False)
    cli.main(["turiz_app", "inicio", "--etapa", "Lendo o app"])
    d = json.load(open("status/turiz_app.json"))
    assert d["estado"] == "rodando" and d["etapa"] == "Lendo o app"
    cli.main(["turiz_app", "fim", "concluido", "--mensagem", "ok", "--total", "lugares=10"])
    d = json.load(open("status/turiz_app.json"))
    assert d["estado"] == "concluido" and d["percentual"] == 100


def test_batimento_mantem_o_bot_vivo_sem_progresso(tmp_path):
    import time as _t
    with bot("receita", publicador=None, pasta=str(tmp_path), batimento_s=0.05) as r:
        antes = json.load(open(tmp_path / "receita.json"))["atualizado_em"]
        _t.sleep(1.2)   # sem nenhuma chamada de progresso: só a thread de batimento
        depois = json.load(open(tmp_path / "receita.json"))["atualizado_em"]
    assert depois > antes
    assert json.load(open(tmp_path / "receita.json"))["estado"] == "concluido"


def test_guarda_de_pausa_do_core(tmp_path, monkeypatch):
    import httpx
    monkeypatch.setenv("TURIZ_STATUS_PUBLICAR", "1")

    def cliente(cfg, codigo=200):
        return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(codigo, json=cfg)))
    assert status.pausado("osm", cliente({"global": {"pausado": True}, "bots": {}})) == (True, "Automação pausada no painel (pausa geral)")
    assert status.pausado("osm", cliente({"global": {"pausado": False}, "bots": {"osm": {"ativo": False}}}))[0] is True
    assert status.pausado("imagens", cliente({"global": {"pausado": False}, "bots": {"osm": {"ativo": False}}}))[0] is False
    assert status.pausado("osm", cliente({}, 404)) == (False, "")                     # Core ainda não existe: segue
    monkeypatch.setattr(status.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("sem rede")))
    assert status.pausado("osm") == (False, "")                                       # sem rede: não pausa
    monkeypatch.delenv("TURIZ_STATUS_PUBLICAR")
    assert status.pausado("osm", cliente({"global": {"pausado": True}})) == (False, "")   # fora do GitHub Actions nunca pausa


def test_bot_pausado_encerra_com_sucesso_e_registra(tmp_path, monkeypatch):
    monkeypatch.setattr(status, "pausado", lambda b, cliente=None: (True, "Bot desligado no painel"))
    executou = []
    with pytest.raises(SystemExit) as e:
        with bot("imagens", publicador=None, pasta=str(tmp_path)):
            executou.append(1)
    assert e.value.code == 0 and executou == []
    d = json.load(open(tmp_path / "imagens.json"))
    assert d["estado"] == "pausado" and "desligado" in d["mensagem"]
