import base64
import json
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import pytest

from core import despachante as D, fila as F
from core.store import ArquivoStore, Conflito, GitHubStore, atualizar

UTC = timezone.utc
T0 = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
REG = [
    {"id": "a", "nome": "A", "grupo": "Lugares", "workflow": "a.yml", "encadeia": True, "entradas": {"x": "1"}, "agenda": "x", "descricao": "", "requer": []},
    {"id": "b", "nome": "B", "grupo": "Lugares", "workflow": "b.yml", "agenda": "x", "descricao": "", "requer": []},
    {"id": "c", "nome": "C", "grupo": "Sistema Turiz", "workflow": None, "agenda": "x", "descricao": "", "requer": []},
]


class FakeLanc:
    def __init__(self):
        self.disparos, self.estados, self.externos, self.cancelados, self.prox, self.erro = [], {}, [], [], 1000, None

    def disparar(self, wf, inputs=None, esperas=()):
        if self.erro:
            raise RuntimeError(self.erro)
        self.prox += 1
        self.disparos.append((wf, inputs, self.prox))
        self.estados[self.prox] = "em_andamento"
        return self.prox

    def estado(self, rid):
        return self.estados.get(rid, "desconhecido"), {}

    def achar_execucao(self, wf, desde):
        return None

    def cancelar(self, rid):
        self.cancelados.append(rid)
        return True

    def ocupado(self, wfs, ignorar=frozenset()):
        return list(self.externos)


def enfileirar(store, bot, agora=T0, **kw):
    return atualizar(store, D.FILA, lambda f: F.nova(f, bot, agora, **kw) and f, F.vazia, "t")


def configurar(store, **mudancas):
    def fn(c):
        c = D.mesclar_config(c, REG)
        for k, v in mudancas.items():
            alvo, _, campo = k.partition("__")
            (c["global"] if alvo == "global" else c["bots"][alvo]).update(v) if isinstance(v, dict) else None
        return c
    return atualizar(store, D.CFG, fn, lambda: {}, "t")


def tarefas(store):
    return store.ler(D.FILA)[0]["tarefas"]


@pytest.fixture
def ctx(tmp_path):
    return ArquivoStore(str(tmp_path)), FakeLanc()


def test_ciclo_completo_dispara_acompanha_e_conclui(ctx):
    store, lanc = ctx
    enfileirar(store, "a", origem="painel")
    r = D.ciclo(store, lanc, REG, T0)
    assert lanc.disparos == [("a.yml", {"x": "1", "encadear": "false"}, 1001)]        # entradas do bot + não encadear a cadeia antiga
    t = tarefas(store)[0]
    assert t["estado"] == "executando" and t["run_id"] == 1001 and t["tentativas"] == 1 and r["iniciadas"] == [t["id"]]
    D.ciclo(store, lanc, REG, T0 + timedelta(minutes=10))
    assert len(lanc.disparos) == 1                                                    # ainda rodando: não dispara de novo
    lanc.estados[1001] = "sucesso"
    status = {"estado": "concluido", "contagem": {"captados": 9, "novos": 5, "atualizados": 4}}
    D.ciclo(store, lanc, REG, T0 + timedelta(minutes=70), ler_status=lambda bot: status)
    t = tarefas(store)[0]
    assert t["estado"] == "concluida" and t["contagens"]["novos"] == 5 and t["duracao_s"] == 70 * 60
    bots = {b["id"]: b for b in store.ler(D.BOTS)[0]["bots"]}
    assert bots["a"]["estatisticas"]["sucessos"] == 1 and bots["a"]["estatisticas"]["contagens"]["captados"] == 9
    assert "saidas" not in bots["a"] and bots["a"]["config"]["gerenciado"] is False


def test_pausa_global_e_bot_desligado_nao_iniciam(ctx):
    store, lanc = ctx
    enfileirar(store, "a")
    enfileirar(store, "b")
    configurar(store, global__={"pausado": True})
    D.ciclo(store, lanc, REG, T0)
    assert lanc.disparos == []
    configurar(store, global__={"pausado": False}, b__={"ativo": False})
    D.ciclo(store, lanc, REG, T0 + timedelta(minutes=1))
    assert [d[0] for d in lanc.disparos] == ["a.yml"]                                  # b está desligado: continua esperando
    assert next(t for t in tarefas(store) if t["bot"] == "b")["estado"] == "aguardando"


def test_nao_inicia_se_ha_bot_rodando_fora_do_core(ctx):
    store, lanc = ctx
    enfileirar(store, "a")
    lanc.externos = ["enderecos.yml"]                                                  # cadeia antiga em andamento
    r = D.ciclo(store, lanc, REG, T0)
    assert lanc.disparos == [] and r["externos"] == ["enderecos.yml"]
    lanc.externos = []
    D.ciclo(store, lanc, REG, T0 + timedelta(minutes=10))
    assert len(lanc.disparos) == 1


def test_concorrencia_maxima_e_prioridade(ctx):
    store, lanc = ctx
    enfileirar(store, "a", prioridade="baixa")
    enfileirar(store, "b", prioridade="critica")
    D.ciclo(store, lanc, REG, T0)
    assert [d[0] for d in lanc.disparos] == ["b.yml"]                                  # max_concorrencia 1: a crítica vai primeiro
    configurar(store, global__={"max_concorrencia": 2})
    D.ciclo(store, lanc, REG, T0 + timedelta(minutes=1))
    assert [d[0] for d in lanc.disparos] == ["b.yml", "a.yml"]


def test_falha_reprograma_com_backoff_e_vai_para_dead_letter(ctx):
    store, lanc = ctx
    enfileirar(store, "a", max_tentativas=2)
    rng = random.Random(0)
    D.ciclo(store, lanc, REG, T0, rng=rng)
    lanc.estados[1001] = "falha"
    D.ciclo(store, lanc, REG, T0 + timedelta(minutes=5), rng=rng)
    t = tarefas(store)[0]
    assert t["estado"] == "programada" and t["erro"] and parse_ok(t["programada_para"]) > T0 + timedelta(minutes=5)
    D.ciclo(store, lanc, REG, T0 + timedelta(minutes=6), rng=rng)
    assert len(lanc.disparos) == 1                                                     # ainda no backoff: não dispara
    depois = T0 + timedelta(hours=2)
    D.ciclo(store, lanc, REG, depois, rng=rng)
    assert len(lanc.disparos) == 2
    lanc.estados[1002] = "falha"
    r = D.ciclo(store, lanc, REG, depois + timedelta(minutes=5), rng=rng)
    fila = store.ler(D.FILA)[0]
    assert fila["tarefas"] == [] and fila["dlq"][0]["bot"] == "a" and r["falhas"] == [fila["dlq"][0]["id"]]
    assert store.ler(D.RESUMO)[0]["fila"]["dead_letter"] == 1


def parse_ok(s):
    return datetime.fromisoformat(s)


def test_erro_ao_disparar_vira_retry_e_bot_sem_workflow_falha(ctx):
    store, lanc = ctx
    enfileirar(store, "a")
    lanc.erro = "GitHub recusou"
    D.ciclo(store, lanc, REG, T0)
    t = tarefas(store)[0]
    assert t["estado"] == "programada" and "GitHub recusou" in t["erro"]
    enfileirar(store, "c")
    lanc.erro = None
    D.ciclo(store, lanc, REG, T0 + timedelta(hours=3))
    c = next(t for t in tarefas(store) if t["bot"] == "c")
    assert "sem workflow" in c["erro"]


def test_status_do_bot_define_parcial_ou_falha(ctx):
    store, lanc = ctx
    for estado_bot, esperado in (("avisos", "concluida_parcial"), ("aguardando_credencial", "concluida_parcial")):
        enfileirar(store, "a", parametros={"n": estado_bot})
        D.ciclo(store, lanc, REG, T0)
        rid = lanc.prox
        lanc.estados[rid] = "sucesso"
        D.ciclo(store, lanc, REG, T0 + timedelta(minutes=5), ler_status=lambda bot, e=estado_bot: {"estado": e, "contagem": {"falhas": 2, "bloqueados": 1}, "mensagem": "m"})
        t = next(t for t in tarefas(store) if t["parametros"].get("n") == estado_bot)
        assert t["estado"] == esperado and t["contagens"]["rejeitados"] == 3


def test_agenda_gerenciada_cria_uma_tarefa_por_ocorrencia(ctx):
    store, lanc = ctx
    configurar(store, a__={"gerenciado": True, "agenda": {"tipo": "diaria", "horas": ["09:00"]}, "prioridade": "alta"})
    sp = ZoneInfo("America/Sao_Paulo")
    agora = datetime(2026, 11, 23, 9, 3, tzinfo=sp).astimezone(UTC)
    D.ciclo(store, lanc, REG, agora)
    ts = tarefas(store)
    assert len(ts) == 1 and ts[0]["origem"] == "agenda" and ts[0]["prioridade"] == "alta"
    lanc.estados[lanc.prox] = "sucesso"
    D.ciclo(store, lanc, REG, agora + timedelta(minutes=20))
    D.ciclo(store, lanc, REG, agora + timedelta(minutes=30))
    assert len([t for t in tarefas(store) if t["bot"] == "a"]) == 1                    # a mesma ocorrência não repete
    prox = {b["id"]: b for b in store.ler(D.BOTS)[0]["bots"]}["a"]["proxima_execucao"]
    assert prox.startswith("2026-11-24T12:00")                                         # 09:00 de Brasília do dia seguinte, em UTC


def test_bot_apos_outro_e_depende_de(ctx):
    store, lanc = ctx
    configurar(store, b__={"gerenciado": True, "agenda": {"tipo": "apos", "bots": ["a"]}})
    enfileirar(store, "a")
    D.ciclo(store, lanc, REG, T0)
    lanc.estados[1001] = "sucesso"
    D.ciclo(store, lanc, REG, T0 + timedelta(minutes=5), ler_status=lambda b: {"estado": "concluido"})   # a termina -> b é criado
    D.ciclo(store, lanc, REG, T0 + timedelta(minutes=6))
    assert [d[0] for d in lanc.disparos] == ["a.yml", "b.yml"]
    assert next(t for t in tarefas(store) if t["bot"] == "b")["origem"] == "dependencia"
    # depende_de: c só roda quando a não tem tarefa ativa
    store2 = ArquivoStore(str(store.pasta) + "_2")
    configurar(store2, b__={"depende_de": ["a"]})
    enfileirar(store2, "a")
    enfileirar(store2, "b")
    l2 = FakeLanc()
    configurar(store2, global__={"max_concorrencia": 3})
    D.ciclo(store2, l2, REG, T0)
    assert [d[0] for d in l2.disparos] == ["a.yml"]


def test_tempo_esgotado_cancela_e_reprograma(ctx):
    store, lanc = ctx
    enfileirar(store, "a")
    configurar(store, a__={"limites": {"max_minutos": 10, "lote": None}})
    D.ciclo(store, lanc, REG, T0)
    D.ciclo(store, lanc, REG, T0 + timedelta(minutes=20))
    assert lanc.cancelados == [1001]
    assert tarefas(store)[0]["estado"] == "programada" and "tempo esgotado" in tarefas(store)[0]["erro"]


def test_bot_novo_no_registro_aparece_sozinho_com_config_padrao(ctx):
    store, lanc = ctx
    D.ciclo(store, lanc, REG, T0)
    novo = REG + [{"id": "z", "nome": "Z", "grupo": "Lugares", "workflow": "z.yml", "agenda": "x", "descricao": "", "requer": [], "gerenciado": True,
                   "agenda_core": {"tipo": "intervalo", "minutos": 60}}]
    D.ciclo(store, lanc, novo, T0 + timedelta(minutes=10))
    bots = {b["id"]: b for b in store.ler(D.BOTS)[0]["bots"]}
    assert bots["z"]["config"]["gerenciado"] is True and bots["z"]["agenda_texto"] == "A cada 1 h"
    assert any(t["bot"] == "z" and t["origem"] == "agenda" for t in tarefas(store))


# ---------- armazenamento ----------
def test_conflito_de_gravacao_refaz_sem_perder_nem_duplicar(tmp_path):
    store = ArquivoStore(str(tmp_path))
    atualizar(store, "x.json", lambda d: {"n": 1}, lambda: {}, "t")
    chamadas = {"n": 0}

    def fn(d):
        chamadas["n"] += 1
        if chamadas["n"] == 1:   # outro escritor muda o arquivo no meio da leitura-modificação-gravação
            store.gravar("x.json", {"n": 100}, store.ler("x.json")[1], "outro")
        d["n"] += 1
        return d
    assert atualizar(store, "x.json", fn, lambda: {}, "t") == {"n": 101} and chamadas["n"] == 2


def test_github_store_cria_branch_orfao_le_e_grava_com_sha(tmp_path):
    arquivos, sha, criado, chamadas = {}, {"v": 0}, [], []

    def h(req):
        m, p = req.method, req.url.path
        chamadas.append((m, p))
        if p.endswith("/git/ref/heads/bot-control"):
            return httpx.Response(200 if criado else 404, json={})
        if p.endswith("/git/trees"):
            return httpx.Response(201, json={"sha": "t"})
        if p.endswith("/git/commits"):
            assert json.loads(req.content)["parents"] == []
            return httpx.Response(201, json={"sha": "c"})
        if p.endswith("/git/refs"):
            criado.append(1)
            return httpx.Response(201, json={})
        if "/contents/" in p:
            nome = p.split("/contents/")[1]
            if m == "GET":
                if nome not in arquivos:
                    return httpx.Response(404)
                return httpx.Response(200, json={"sha": arquivos[nome][1], "content": base64.b64encode(arquivos[nome][0]).decode()})
            corpo = json.loads(req.content)
            assert corpo["branch"] == "bot-control"
            if nome in arquivos and corpo.get("sha") != arquivos[nome][1]:
                return httpx.Response(409)
            sha["v"] += 1
            arquivos[nome] = (base64.b64decode(corpo["content"]), f"s{sha['v']}")
            return httpx.Response(201 if corpo.get("sha") is None else 200, json={})
        return httpx.Response(500)
    st = GitHubStore("o/r", "tok", client=httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(h)))
    assert st.ler("control/config.json") == (None, None)
    atualizar(st, "control/config.json", lambda d: {"a": 1}, lambda: {}, "t")
    assert ("POST", "/repos/o/r/git/refs") in chamadas
    atualizar(st, "control/config.json", lambda d: {**d, "b": 2}, lambda: {}, "t")
    assert st.ler("control/config.json")[0] == {"a": 1, "b": 2}
    with pytest.raises(Conflito):
        st.gravar("control/config.json", {"x": 1}, "sha-velho", "t")


class ContaGravacoes(ArquivoStore):
    def __init__(self, pasta):
        super().__init__(pasta)
        self.n = 0

    def gravar(self, *a, **k):
        self.n += 1
        return super().gravar(*a, **k)


def test_ciclo_sem_novidade_nao_gera_gravacoes(tmp_path):
    store, lanc = ContaGravacoes(str(tmp_path)), FakeLanc()
    D.ciclo(store, lanc, REG, T0)                       # primeiro ciclo cria os arquivos
    antes = store.n
    for i in range(1, 4):                               # 3 ciclos seguidos (10, 20 e 29 min depois) sem nada novo
        D.ciclo(store, lanc, REG, T0 + timedelta(minutes=[10, 20, 29][i - 1]))
    assert store.n == antes                             # nenhum commit extra: só o batimento a cada 30 min
    D.ciclo(store, lanc, REG, T0 + timedelta(minutes=31))
    assert store.n > antes
