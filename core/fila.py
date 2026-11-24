"""Fila central de tarefas: prioridade, deduplicação, retry com backoff exponencial + jitter, dead-letter queue, expiração e limpeza.

Opera sobre um dicionário `fila` ({"versao", "meta", "tarefas", "dlq"}) que o despachante guarda em control/fila.json.
Nenhuma função faz rede; o tempo e o gerador de aleatoriedade entram por parâmetro (testável)."""
import hashlib
import json
import random
import uuid
from datetime import datetime, timedelta

from .modelos import ATIVOS, EM_ESPERA, FINAIS, PRIORIDADES, iso, parse

CONTAGENS = ("captados", "novos", "atualizados", "duplicados", "rejeitados")
MAX_LOGS = 20


def vazia() -> dict:
    return {"versao": 1, "meta": {"ultimo_agendado": {}, "apos_visto": {}, "ultimo_ciclo": None}, "tarefas": [], "dlq": []}


def chave_dedup(bot, tipo, regiao, registro, parametros) -> str:
    base = json.dumps([bot, tipo, regiao, registro, parametros or {}], sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(base.encode(), usedforsecurity=False).hexdigest()[:16]


def log(t: dict, msg: str, agora: datetime):
    t["logs"] = (t.get("logs", []) + [f"{iso(agora)[11:19]} {msg}"[:200]])[-MAX_LOGS:]


def nova(fila: dict, bot: str, agora: datetime, tipo="executar", prioridade="normal", origem="manual", parametros=None, regiao=None,
         registro=None, programada_para: datetime | None = None, max_tentativas=3):
    """Cria uma tarefa. Retorna (tarefa, criada). Se já houver tarefa ativa igual, devolve a existente (não duplica)."""
    if prioridade not in PRIORIDADES:
        raise ValueError(f"prioridade inválida: {prioridade}")
    chave = chave_dedup(bot, tipo, regiao, registro, parametros)
    for t in fila["tarefas"]:
        if t["chave"] == chave and t["estado"] in ATIVOS:
            return t, False
    estado = "programada" if programada_para and programada_para > agora else "aguardando"
    t = {"id": uuid.uuid4().hex[:12], "bot": bot, "tipo": tipo, "prioridade": prioridade, "origem": origem, "regiao": regiao, "registro": registro,
         "parametros": parametros or {}, "criada_em": iso(agora), "programada_para": iso(programada_para) if programada_para else None,
         "iniciada_em": None, "finalizada_em": None, "duracao_s": None, "tentativas": 0, "max_tentativas": max_tentativas, "estado": estado,
         "resultado": None, "erro": None, "logs": [], "contagens": {k: 0 for k in CONTAGENS}, "run_id": None, "chave": chave}
    log(t, f"criada ({origem}, prioridade {prioridade})", agora)
    fila["tarefas"].append(t)
    return t, True


def _ordem(t):
    return (PRIORIDADES.index(t["prioridade"]), t.get("programada_para") or t["criada_em"], t["criada_em"])


def proximas(fila: dict, agora: datetime, vagas: int, bots_bloqueados=()) -> list[dict]:
    """Tarefas prontas para iniciar, na ordem prioridade -> programação -> criação, no máximo `vagas`, uma por bot."""
    ocupados = {t["bot"] for t in fila["tarefas"] if t["estado"] == "executando"} | set(bots_bloqueados)
    prontas = [t for t in fila["tarefas"] if t["estado"] in EM_ESPERA and (not t.get("programada_para") or parse(t["programada_para"]) <= agora)]
    escolhidas = []
    for t in sorted(prontas, key=_ordem):
        if len(escolhidas) >= vagas:
            break
        if t["bot"] in ocupados:
            continue
        escolhidas.append(t)
        ocupados.add(t["bot"])
    return escolhidas


def iniciar(t: dict, agora: datetime, run_id=None):
    t["estado"], t["iniciada_em"], t["tentativas"], t["run_id"] = "executando", iso(agora), t["tentativas"] + 1, run_id
    log(t, f"iniciada (tentativa {t['tentativas']})" + (f", execução {run_id}" if run_id else ""), agora)


def _fechar(t: dict, estado: str, agora: datetime):
    t["estado"], t["finalizada_em"] = estado, iso(agora)
    if t.get("iniciada_em"):
        t["duracao_s"] = max(0, int((agora - parse(t["iniciada_em"])).total_seconds()))


def concluir(t: dict, agora: datetime, contagens: dict | None = None, parcial=False, resultado=None):
    for k, v in (contagens or {}).items():
        if k in CONTAGENS and isinstance(v, int):
            t["contagens"][k] = v
    t["resultado"] = resultado
    _fechar(t, "concluida_parcial" if parcial else "concluida", agora)
    log(t, "concluída parcialmente" if parcial else "concluída", agora)


def backoff_s(tentativas: int, cfg: dict, rng=random) -> float:
    """Espera antes da próxima tentativa: base * 2^(n-1), limitada ao teto, com jitter ±cfg['jitter']."""
    bruto = min(cfg["teto_s"], cfg["base_s"] * 2 ** max(0, tentativas - 1))
    return bruto * (1 + rng.uniform(-cfg["jitter"], cfg["jitter"]))


def falhar(fila: dict, t: dict, erro: str, agora: datetime, cfg: dict, rng=random) -> str:
    """Registra a falha. Retorna 'retry' (reprogramada) ou 'dlq' (tentativas esgotadas -> dead-letter queue)."""
    t["erro"] = str(erro)[:300]
    if t["tentativas"] >= t["max_tentativas"]:
        _fechar(t, "falhou", agora)
        log(t, f"falhou definitivamente: {t['erro']}", agora)
        fila["tarefas"] = [x for x in fila["tarefas"] if x["id"] != t["id"]]
        fila["dlq"].append(t)
        return "dlq"
    espera = backoff_s(t["tentativas"], cfg, rng)
    t["estado"], t["programada_para"], t["run_id"] = "programada", iso(agora + timedelta(seconds=espera)), None
    log(t, f"falhou ({t['erro']}); nova tentativa em {int(espera)} s", agora)
    return "retry"


def cancelar(t: dict, agora: datetime):
    if t["estado"] in FINAIS:
        return False
    _fechar(t, "cancelada", agora)
    log(t, "cancelada", agora)
    return True


def pausar(t: dict, agora: datetime):
    if t["estado"] in EM_ESPERA or t["estado"] == "criada":
        t["estado"] = "pausada"
        log(t, "pausada", agora)
        return True
    return False


def retomar(t: dict, agora: datetime):
    if t["estado"] == "pausada":
        t["estado"] = "aguardando"
        log(t, "retomada", agora)
        return True
    return False


def expirar(fila: dict, agora: datetime, ttl_horas: int) -> int:
    n = 0
    for t in fila["tarefas"]:
        if t["estado"] in EM_ESPERA | {"criada", "pausada"}:
            ref = parse(t.get("programada_para") or t["criada_em"])
            if agora - ref > timedelta(hours=ttl_horas):
                _fechar(t, "expirada", agora)
                log(t, "expirada na fila", agora)
                n += 1
    return n


def reprocessar(fila: dict, tarefa_id: str, agora: datetime):
    """Tira uma tarefa da dead-letter queue e cria outra igual (tentativas zeradas). Retorna a nova tarefa ou None."""
    alvo = next((t for t in fila["dlq"] if t["id"] == tarefa_id), None)
    if not alvo:
        return None
    fila["dlq"] = [t for t in fila["dlq"] if t["id"] != tarefa_id]
    novo, _ = nova(fila, alvo["bot"], agora, alvo["tipo"], alvo["prioridade"], "manual", alvo["parametros"], alvo["regiao"], alvo["registro"], None, alvo["max_tentativas"])
    log(novo, f"reprocessada da dead-letter {tarefa_id}", agora)
    return novo


def limpar(fila: dict, agora: datetime, retencao_dias: int, estados=("expirada", "cancelada", "concluida", "concluida_parcial"), maximo=400) -> dict:
    """Remove só tarefas finalizadas nos estados dados e mais antigas que a retenção (regra explícita), e limita o histórico a `maximo`.
    Nunca toca em tarefas ativas nem na dead-letter queue."""
    corte = agora - timedelta(days=retencao_dias)
    antes = len(fila["tarefas"])
    fila["tarefas"] = [t for t in fila["tarefas"] if not (t["estado"] in estados and parse(t["finalizada_em"] or t["criada_em"]) < corte)]
    finais = sorted([t for t in fila["tarefas"] if t["estado"] in FINAIS], key=lambda t: t["finalizada_em"] or "")
    excesso = max(0, len(finais) - maximo)
    if excesso:
        ids = {t["id"] for t in finais[:excesso]}
        fila["tarefas"] = [t for t in fila["tarefas"] if t["id"] not in ids]
    return {"removidas": antes - len(fila["tarefas"])}


def resumo(fila: dict) -> dict:
    por_estado, por_prio, por_bot = {}, {}, {}
    for t in fila["tarefas"]:
        por_estado[t["estado"]] = por_estado.get(t["estado"], 0) + 1
        if t["estado"] in ATIVOS:
            por_prio[t["prioridade"]] = por_prio.get(t["prioridade"], 0) + 1
            por_bot[t["bot"]] = por_bot.get(t["bot"], 0) + 1
    return {"por_estado": por_estado, "ativas_por_prioridade": por_prio, "ativas_por_bot": por_bot,
            "na_fila": sum(por_estado.get(e, 0) for e in ("aguardando", "programada", "criada")), "executando": por_estado.get("executando", 0),
            "dead_letter": len(fila["dlq"])}
