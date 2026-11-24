import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from core import agenda, fila as F
from core.modelos import config_global_padrao, iso

UTC = timezone.utc
SP = ZoneInfo("America/Sao_Paulo")


def sp(ano, mes, dia, h, m=0):
    return datetime(ano, mes, dia, h, m, tzinfo=SP).astimezone(UTC)


# ---------- agenda ----------
def test_diaria_usa_horario_de_brasilia():
    ag = {"tipo": "diaria", "horas": ["11:07"]}
    # 14:10 UTC = 11:10 em Brasília (UTC-3): a ocorrência de 11:07 acabou de passar
    ok, oc = agenda.avaliar(ag, datetime(2026, 11, 23, 14, 10, tzinfo=UTC), None)
    assert ok and oc == datetime(2026, 11, 23, 14, 7, tzinfo=UTC)
    # antes do horário local (10:50 em Brasília) a de ontem já foi tratada
    ontem = datetime(2026, 11, 22, 14, 7, tzinfo=UTC)
    assert agenda.avaliar(ag, datetime(2026, 11, 23, 13, 50, tzinfo=UTC), ontem) == (False, None)


def test_nao_executa_duas_vezes_a_mesma_ocorrencia():
    ag = {"tipo": "diaria", "horas": ["06:00"]}
    agora = sp(2026, 11, 23, 6, 5)
    ok, oc = agenda.avaliar(ag, agora, None)
    assert ok
    assert agenda.avaliar(ag, agora + timedelta(minutes=10), oc) == (False, None)


def test_ocorrencia_muito_atrasada_e_pulada_mas_marcada():
    ag = {"tipo": "diaria", "horas": ["06:00"]}
    ok, oc = agenda.avaliar(ag, sp(2026, 11, 23, 15, 0), None)     # 9 h depois: passou da janela de 6 h
    assert ok is False and oc == sp(2026, 11, 23, 6, 0)            # devolve a ocorrência para o chamador marcar como vista


def test_semanal_respeita_dias_e_proxima():
    ag = {"tipo": "semanal", "dias": [0], "horas": ["03:00"]}      # segunda 03:00
    seg = sp(2026, 11, 23, 3, 10)                                  # 23/11/2026 é segunda
    assert agenda.avaliar(ag, seg, None)[0] is True
    ter = sp(2026, 11, 24, 12, 0)
    assert agenda.avaliar(ag, ter, sp(2026, 11, 23, 3, 0)) == (False, None)
    assert agenda.proxima(ag, ter, None) == sp(2026, 11, 30, 3, 0)


def test_intervalo_e_unica_e_validacao():
    t0 = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    ag = {"tipo": "intervalo", "minutos": 60}
    assert agenda.avaliar(ag, t0, None)[0] is True
    assert agenda.avaliar(ag, t0 + timedelta(minutes=59), t0)[0] is False
    assert agenda.avaliar(ag, t0 + timedelta(minutes=60), t0)[0] is True
    un = {"tipo": "unica", "em": "2026-11-24T09:00:00-03:00"}
    assert agenda.avaliar(un, sp(2026, 11, 24, 9, 5), None)[0] is True
    assert agenda.avaliar(un, sp(2026, 11, 24, 9, 5), sp(2026, 11, 24, 9, 0))[0] is False
    assert agenda.validar({"tipo": "diaria", "horas": ["25:00"]}) and agenda.validar({"tipo": "xyz"}) and agenda.validar({"tipo": "intervalo", "minutos": 1})
    assert agenda.avaliar({"tipo": "diaria", "horas": ["99:99"]}, t0, None) == (False, None)
    assert agenda.descrever({"tipo": "semanal", "dias": [0, 3], "horas": ["07:00"]}) == "seg, qui 07:00"


# ---------- fila ----------
def test_prioridade_e_ordem_e_uma_tarefa_por_bot():
    f, agora = F.vazia(), datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    F.nova(f, "a", agora, prioridade="baixa")
    F.nova(f, "b", agora + timedelta(seconds=1), prioridade="critica")
    F.nova(f, "c", agora + timedelta(seconds=2), prioridade="alta")
    F.nova(f, "c", agora, tipo="buscar_fotos", prioridade="normal")          # mesmo bot "c": só uma por vez
    assert [t["bot"] for t in F.proximas(f, agora + timedelta(minutes=1), 3)] == ["b", "c", "a"]
    assert len(F.proximas(f, agora + timedelta(minutes=1), 1)) == 1


def test_deduplica_tarefa_ativa_igual():
    f, agora = F.vazia(), datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    t1, nova1 = F.nova(f, "osm", agora, parametros={"x": 1})
    t2, nova2 = F.nova(f, "osm", agora, parametros={"x": 1})
    assert nova1 and not nova2 and t1 is t2 and len(f["tarefas"]) == 1
    F.cancelar(t1, agora)
    assert F.nova(f, "osm", agora, parametros={"x": 1})[1] is True           # depois de finalizada, pode criar de novo
    with pytest.raises(ValueError):
        F.nova(f, "osm", agora, prioridade="urgentissima")


def test_programada_para_o_futuro_espera():
    f, agora = F.vazia(), datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    t, _ = F.nova(f, "osm", agora, programada_para=agora + timedelta(hours=1))
    assert t["estado"] == "programada" and F.proximas(f, agora, 5) == []
    assert F.proximas(f, agora + timedelta(hours=1, seconds=1), 5) == [t]


def test_backoff_exponencial_com_jitter_e_dead_letter():
    cfg = config_global_padrao()["retry"]
    rng = random.Random(1)
    esperas = [F.backoff_s(n, {**cfg, "jitter": 0}, rng) for n in (1, 2, 3, 4, 10)]
    assert esperas == [120, 240, 480, 960, 3600]                             # dobra a cada tentativa e respeita o teto
    for n in (1, 2, 3):
        e = F.backoff_s(n, cfg, rng)
        base = min(cfg["teto_s"], cfg["base_s"] * 2 ** (n - 1))
        assert base * 0.75 <= e <= base * 1.25                               # jitter de ±25%
    f, agora = F.vazia(), datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    t, _ = F.nova(f, "osm", agora, max_tentativas=2)
    F.iniciar(t, agora)
    assert F.falhar(f, t, "boom", agora, cfg, rng) == "retry" and t["estado"] == "programada" and t["programada_para"] > iso(agora)
    F.iniciar(t, agora + timedelta(hours=1))
    assert F.falhar(f, t, "boom de novo", agora + timedelta(hours=1), cfg, rng) == "dlq"
    assert f["tarefas"] == [] and f["dlq"][0]["estado"] == "falhou" and f["dlq"][0]["erro"] == "boom de novo"
    novo = F.reprocessar(f, f["dlq"][0]["id"], agora + timedelta(hours=2))
    assert novo["tentativas"] == 0 and novo["estado"] == "aguardando" and f["dlq"] == [] and novo["origem"] == "manual"


def test_concluir_contagens_duracao_e_parcial():
    f, agora = F.vazia(), datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    t, _ = F.nova(f, "enderecos", agora)
    F.iniciar(t, agora)
    F.concluir(t, agora + timedelta(seconds=90), {"captados": 10, "novos": 3, "inexistente": 9}, parcial=True)
    assert t["estado"] == "concluida_parcial" and t["duracao_s"] == 90 and t["contagens"]["novos"] == 3 and "inexistente" not in t["contagens"]


def test_expirar_pausar_retomar_cancelar():
    f, agora = F.vazia(), datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    velha, _ = F.nova(f, "a", agora - timedelta(hours=30))
    nova_t, _ = F.nova(f, "b", agora)
    assert F.expirar(f, agora, 24) == 1 and velha["estado"] == "expirada" and nova_t["estado"] == "aguardando"
    assert F.pausar(nova_t, agora) and nova_t["estado"] == "pausada" and F.proximas(f, agora, 5) == []
    assert F.retomar(nova_t, agora) and nova_t["estado"] == "aguardando"
    assert F.cancelar(nova_t, agora) and not F.cancelar(nova_t, agora)


def test_limpar_so_remove_finalizadas_antigas_e_preserva_ativas_e_dlq():
    f, agora = F.vazia(), datetime(2026, 12, 20, 12, 0, tzinfo=UTC)
    velha, _ = F.nova(f, "a", agora - timedelta(days=30))
    F.cancelar(velha, agora - timedelta(days=30))
    recente, _ = F.nova(f, "b", agora - timedelta(days=1))
    F.cancelar(recente, agora - timedelta(days=1))
    ativa, _ = F.nova(f, "c", agora - timedelta(days=40))                      # ativa e antiga: não pode ser removida
    f["dlq"].append({"id": "x", "estado": "falhou"})
    assert F.limpar(f, agora, 14) == {"removidas": 1}
    ids = {t["id"] for t in f["tarefas"]}
    assert recente["id"] in ids and ativa["id"] in ids and velha["id"] not in ids and f["dlq"] == [{"id": "x", "estado": "falhou"}]
    r = F.resumo(f)
    assert r["dead_letter"] == 1 and r["ativas_por_bot"] == {"c": 1}
