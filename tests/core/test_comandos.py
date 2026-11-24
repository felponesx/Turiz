import json
from datetime import datetime, timedelta, timezone

import pytest

from core import comandos as C, despachante as D, fila as F
from core.store import ArquivoStore

T0 = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
REG = [{"id": "a", "nome": "A", "grupo": "Lugares", "workflow": "a.yml", "agenda": "x", "descricao": "", "requer": []},
       {"id": "b", "nome": "B", "grupo": "Lugares", "workflow": "b.yml", "agenda": "x", "descricao": "", "requer": []},
       {"id": "c", "nome": "C", "grupo": "Sistema Turiz", "workflow": None, "agenda": "x", "descricao": "", "requer": []}]


class Lanc:
    def __init__(self):
        self.n, self.cancelados, self.estados = 0, [], {}

    def disparar(self, wf, inputs=None, esperas=()):
        self.n += 1
        self.estados[100 + self.n] = "em_andamento"
        return 100 + self.n

    def estado(self, rid):
        return self.estados.get(rid, "desconhecido"), {}

    def achar_execucao(self, *a):
        return None

    def cancelar(self, rid):
        self.cancelados.append(rid)

    def ocupado(self, *a, **k):
        return []


@pytest.fixture
def st(tmp_path):
    return ArquivoStore(str(tmp_path))


def cmd(st, **kw):
    return C.aplicar(st, kw, REG, T0)


def cfg(st):
    return D.mesclar_config(st.ler(C.CFG)[0], REG)


def test_config_bot_valida_e_persiste(st):
    cmd(st, acao="config_bot", bot="a", campos={"ativo": False, "prioridade": "alta", "agenda": {"tipo": "diaria", "horas": ["06:30"]}, "gerenciado": True,
                                                  "limites": {"max_minutos": 90, "lote": 500}, "categorias": ["pizza", "bar"], "regiao": "Pinheiros"})
    c = cfg(st)["bots"]["a"]
    assert c["ativo"] is False and c["prioridade"] == "alta" and c["agenda"]["horas"] == ["06:30"] and c["limites"] == {"max_minutos": 90, "lote": 500}
    assert c["regiao"] == "Pinheiros" and cfg(st)["bots"]["b"]["ativo"] is True       # só o bot pedido mudou


@pytest.mark.parametrize("comando", [
    {"acao": "config_bot", "bot": "nao_existe", "campos": {"ativo": True}},
    {"acao": "config_bot", "bot": "a", "campos": {"ativo": "sim"}},
    {"acao": "config_bot", "bot": "a", "campos": {"prioridade": "urgentissima"}},
    {"acao": "config_bot", "bot": "a", "campos": {"agenda": {"tipo": "diaria", "horas": ["25:99"]}}},
    {"acao": "config_bot", "bot": "a", "campos": {"agenda": {"tipo": "apos", "bots": ["a"]}}},
    {"acao": "config_bot", "bot": "a", "campos": {"depende_de": ["a"]}},
    {"acao": "config_bot", "bot": "a", "campos": {"limites": {"max_minutos": 100000}}},
    {"acao": "config_bot", "bot": "a", "campos": {"max_tentativas": 0}},
    {"acao": "config_bot", "bot": "a", "campos": {"parametros": {"x": "y" * 5000}}},
    {"acao": "config_bot", "bot": "a", "campos": {"campo_inventado": 1}},
    {"acao": "config_bot", "bot": "a", "campos": {}},
    {"acao": "config_global", "campos": {"max_concorrencia": 99}},
    {"acao": "config_global", "campos": {"timezone": "Marte/Olimpo"}},
    {"acao": "enfileirar", "bot": "a", "prioridade": "x"},
    {"acao": "enfileirar", "bot": "a", "programada_para": "ontem de manhã"},
    {"acao": "nao_existe"}, {"sem_acao": 1}, "texto solto", {"acao": "lote", "comandos": []},
    {"acao": "lote", "comandos": [{"acao": "lote", "comandos": [{"acao": "pausar_tudo"}]}]},
])
def test_comandos_invalidos_sao_rejeitados_sem_alterar_nada(st, comando):
    with pytest.raises(C.ErroComando):
        C.aplicar(st, comando, REG, T0)
    assert st.ler(C.CFG)[0] is None and st.ler(C.FILA)[0] is None


def test_pausa_geral_enfileirar_e_dedup(st):
    assert "pausada" in cmd(st, acao="pausar_tudo") and cfg(st)["global"]["pausado"] is True
    assert "retomada" in cmd(st, acao="retomar_tudo") and cfg(st)["global"]["pausado"] is False
    assert "criada" in cmd(st, acao="enfileirar", bot="a", prioridade="critica")
    assert "já existia" in cmd(st, acao="enfileirar", bot="a", prioridade="critica")
    assert len(st.ler(C.FILA)[0]["tarefas"]) == 1


def test_executar_todos_cria_uma_tarefa_por_bot_ativo_com_workflow_em_ordem(st):
    cmd(st, acao="config_bot", bot="b", campos={"ativo": False})
    assert cmd(st, acao="executar_todos").startswith("1 tarefas")       # a (ativo, com workflow); b desligado; c sem workflow
    lanc = Lanc()
    D.ciclo(st, lanc, REG, T0)
    assert lanc.n == 1


def test_cancelar_pausar_retomar_reiniciar_e_dead_letter(st):
    cmd(st, acao="enfileirar", bot="a")
    tid = st.ler(C.FILA)[0]["tarefas"][0]["id"]
    assert cmd(st, acao="pausar_tarefa", id=tid) == "tarefa pausada"
    with pytest.raises(C.ErroComando):
        cmd(st, acao="pausar_tarefa", id=tid)                           # já pausada
    assert cmd(st, acao="retomar_tarefa", id=tid) == "tarefa retomada"
    assert "reiniciado" in cmd(st, acao="reiniciar_bot", bot="a")        # cancela a antiga e cria nova (alta)
    ts = st.ler(C.FILA)[0]["tarefas"]
    assert [t["estado"] for t in ts].count("cancelada") == 1 and ts[-1]["prioridade"] == "alta"
    assert "canceladas" in cmd(st, acao="cancelar_fila")
    with pytest.raises(C.ErroComando):
        cmd(st, acao="reprocessar", id=tid)                              # não está na DLQ
    with pytest.raises(C.ErroComando):
        cmd(st, acao="cancelar_tarefa", id="inexistente")


def test_cancelar_execucao_em_andamento_cancela_no_github(st):
    cmd(st, acao="enfileirar", bot="a")
    lanc = Lanc()
    D.ciclo(st, lanc, REG, T0)
    tid = st.ler(C.FILA)[0]["tarefas"][0]["id"]
    with pytest.raises(C.ErroComando):
        cmd(st, acao="reiniciar_bot", bot="a")                           # rodando: precisa cancelar antes
    assert cmd(st, acao="cancelar_execucao", id=tid) == "cancelamento pedido"
    D.ciclo(st, lanc, REG, T0 + timedelta(minutes=1))
    assert lanc.cancelados == [101] and st.ler(C.FILA)[0]["tarefas"][0]["estado"] == "cancelada"


def test_lote_aplica_varios_comandos_de_uma_vez(st):
    msg = cmd(st, acao="lote", comandos=[{"acao": "config_global", "campos": {"max_concorrencia": 2}},
                                         {"acao": "config_bot", "bot": "a", "campos": {"prioridade": "baixa"}}, {"acao": "pausar_tudo"}])
    assert msg.count(";") == 2 and cfg(st)["global"]["max_concorrencia"] == 2 and cfg(st)["bots"]["a"]["prioridade"] == "baixa"


def test_cli_registra_resultado_e_rejeita_comando_ruim(tmp_path, monkeypatch, capsys):
    pasta = str(tmp_path)
    assert D.main(["--local", pasta, "--comando", json.dumps({"acao": "pausar_tudo"})]) == 0
    assert D.main(["--local", pasta, "--comando", json.dumps({"acao": "config_bot", "bot": "zzz", "campos": {"ativo": True}})]) == 2
    meta = ArquivoStore(pasta).ler(C.FILA)[0]["meta"]["ultimo_comando"]
    assert meta["ok"] is False and "bot desconhecido" in meta["mensagem"]
    assert D.main(["--local", pasta, "--comando", "{isto não é json"]) == 2


def test_contrato_painel_core_payloads_reais_do_painel_sao_aceitos(st):
    """Payloads copiados do que o painel envia (capturados no teste de navegador)."""
    payloads = [
        {"acao": "enfileirar", "bot": "a", "prioridade": "alta"},
        {"acao": "config_bot", "bot": "a", "campos": {"ativo": True, "gerenciado": False, "prioridade": "alta", "agenda": {"tipo": "semanal", "horas": ["07:30", "19:00"], "dias": [0]},
                                                       "max_tentativas": 3, "limites": {"max_minutos": 180, "lote": None}, "regiao": None, "categorias": [], "reprocessar": "ignorar_existentes"}},
        {"acao": "config_bot", "bot": "b", "campos": {"agenda": {"tipo": "intervalo", "minutos": 360}, "gerenciado": True}},
        {"acao": "config_bot", "bot": "b", "campos": {"agenda": {"tipo": "apos", "bots": ["a"]}}},
        {"acao": "config_global", "campos": {"max_concorrencia": 2, "ttl_espera_horas": 24, "retencao_dias": 14}},
        {"acao": "pausar_tudo"}, {"acao": "retomar_tudo"}, {"acao": "executar_todos"}, {"acao": "cancelar_fila"}, {"acao": "limpar"},
    ]
    for p in payloads:
        C.aplicar(st, p, REG, T0)          # nenhum levanta ErroComando
    assert cfg(st)["bots"]["a"]["agenda"]["dias"] == [0] and cfg(st)["bots"]["b"]["agenda"] == {"tipo": "apos", "bots": ["a"]}
