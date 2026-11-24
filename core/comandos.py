"""Comandos do painel para o Core. O painel NÃO escreve nos arquivos de controle: ele dispara o workflow `nucleo.yml` com um comando em JSON
e este módulo valida tudo (tipos, limites, agendas, nomes de bots) antes de aplicar. Quem pode comandar é quem pode disparar workflows no GitHub.

Ações: enfileirar, executar_todos, cancelar_tarefa, cancelar_execucao, pausar_tarefa, retomar_tarefa, reprocessar, reiniciar_bot, cancelar_fila,
       config_bot, config_global, pausar_tudo, retomar_tudo, limpar, lote."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

from . import agenda, fila as F
from .modelos import PRIORIDADES, iso, parse
from .store import atualizar

CFG, FILA = "control/config.json", "control/fila.json"
REPROCESSAR = {"ignorar_existentes", "atualizar_existentes", "tudo"}
LIMITE_JSON = 2048


class ErroComando(ValueError):
    pass


def _exige(cond, msg):
    if not cond:
        raise ErroComando(msg)


def _int(v, lo, hi, nome):
    _exige(isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi, f"{nome}: inteiro entre {lo} e {hi}")
    return v


def _pequeno(v, nome):
    _exige(isinstance(v, dict) and len(json.dumps(v, ensure_ascii=False)) <= LIMITE_JSON, f"{nome}: objeto de até {LIMITE_JSON} caracteres")
    return v


def validar_config_bot(campos: dict, bots_validos: set[str], bot: str) -> dict:
    _exige(isinstance(campos, dict) and campos, "campos: informe ao menos um campo")
    saida = {}
    for k, v in campos.items():
        if k in ("ativo", "gerenciado"):
            _exige(isinstance(v, bool), f"{k}: verdadeiro ou falso")
        elif k == "prioridade":
            _exige(v in PRIORIDADES, f"prioridade: {', '.join(PRIORIDADES)}")
        elif k == "agenda":
            erros = agenda.validar(v)
            _exige(not erros, "agenda: " + "; ".join(erros))
            if v["tipo"] == "apos":
                _exige(all(b in bots_validos and b != bot for b in v["bots"]), "agenda: bots inexistentes ou o próprio bot")
        elif k == "depende_de":
            _exige(isinstance(v, list) and all(b in bots_validos and b != bot for b in v), "depende_de: lista de bots existentes (não o próprio)")
        elif k == "max_tentativas":
            _int(v, 1, 10, k)
        elif k == "limites":
            _exige(isinstance(v, dict), "limites: objeto")
            _int(v.get("max_minutos", 180), 5, 720, "limites.max_minutos")
            _exige(v.get("lote") is None or _int(v["lote"], 1, 1_000_000, "limites.lote"), "limites.lote")
            v = {"max_minutos": v.get("max_minutos", 180), "lote": v.get("lote")}
        elif k in ("parametros", "regras_revisao"):
            _pequeno(v, k)
        elif k == "regiao":
            _exige(v is None or (isinstance(v, str) and len(v) <= 80), "regiao: texto de até 80 caracteres")
        elif k == "categorias":
            _exige(isinstance(v, list) and len(v) <= 50 and all(isinstance(c, str) and len(c) <= 40 for c in v), "categorias: até 50 textos curtos")
        elif k == "reprocessar":
            _exige(v in REPROCESSAR, f"reprocessar: {', '.join(sorted(REPROCESSAR))}")
        else:
            raise ErroComando(f"campo desconhecido: {k}")
        saida[k] = v
    return saida


def validar_config_global(campos: dict) -> dict:
    _exige(isinstance(campos, dict) and campos, "campos: informe ao menos um campo")
    saida = {}
    for k, v in campos.items():
        if k == "pausado":
            _exige(isinstance(v, bool), "pausado: verdadeiro ou falso")
        elif k == "max_concorrencia":
            _int(v, 1, 4, k)
        elif k == "ttl_espera_horas":
            _int(v, 1, 168, k)
        elif k == "retencao_dias":
            _int(v, 1, 90, k)
        elif k == "timezone":
            _exige(v in available_timezones(), "timezone inválido")
            ZoneInfo(v)
        else:
            raise ErroComando(f"campo desconhecido: {k}")
        saida[k] = v
    return saida


def aplicar(store, cmd: dict, registro: list[dict], agora: datetime, depth: int = 0) -> str:
    """Aplica um comando validado. Retorna uma mensagem curta de sucesso; levanta ErroComando se inválido."""
    _exige(isinstance(cmd, dict) and isinstance(cmd.get("acao"), str), "comando: objeto com `acao`")
    acao = cmd["acao"]
    por_id = {b["id"]: b for b in registro}

    def bot_valido():
        b = cmd.get("bot")
        _exige(b in por_id, f"bot desconhecido: {b!r}")
        return b

    def tarefa(f, incluir_dlq=False):
        t = next((x for x in f["tarefas"] + (f["dlq"] if incluir_dlq else []) if x["id"] == cmd.get("id")), None)
        _exige(t is not None, "tarefa não encontrada")
        return t

    if acao == "lote":
        _exige(depth == 0 and isinstance(cmd.get("comandos"), list) and 0 < len(cmd["comandos"]) <= 30, "lote: de 1 a 30 comandos, sem aninhar")
        return "; ".join(aplicar(store, c, registro, agora, depth + 1) for c in cmd["comandos"])

    if acao in ("pausar_tudo", "retomar_tudo"):
        atualizar(store, CFG, lambda c: _g(c, registro, {"pausado": acao == "pausar_tudo"}), lambda: {}, f"core: {acao}")
        return "automação pausada" if acao == "pausar_tudo" else "automação retomada"

    if acao == "config_global":
        campos = validar_config_global(cmd.get("campos"))
        atualizar(store, CFG, lambda c: _g(c, registro, campos), lambda: {}, "core: configuração geral")
        return "configuração geral salva"

    if acao == "config_bot":
        bot = bot_valido()
        campos = validar_config_bot(cmd.get("campos"), set(por_id), bot)

        def fn(c):
            c = _mesclar(c, registro)
            c["bots"][bot].update(campos)
            return c
        atualizar(store, CFG, fn, lambda: {}, f"core: configuração de {bot}")
        return f"{bot}: configuração salva"

    if acao == "enfileirar":
        bot = bot_valido()
        prio = cmd.get("prioridade", "normal")
        _exige(prio in PRIORIDADES, "prioridade inválida")
        try:
            prog = parse(cmd["programada_para"]) if cmd.get("programada_para") else None
        except (ValueError, TypeError):
            raise ErroComando("programada_para: data em ISO 8601") from None
        _pequeno(cmd.get("parametros") or {}, "parametros")
        res = {}

        def fn(f):
            t, criada = F.nova(f, bot, agora, "executar", prio, cmd.get("origem", "painel") if cmd.get("origem") in ("painel", "manual") else "painel",
                               cmd.get("parametros"), cmd.get("regiao"), None, prog)
            res["criada"], res["id"] = criada, t["id"]
            return f
        atualizar(store, FILA, fn, F.vazia, f"core: enfileirar {bot}")
        return f"{bot}: tarefa {'criada' if res['criada'] else 'já existia'} ({res['id']})"

    if acao == "executar_todos":
        cfg = _mesclar(store.ler(CFG)[0] or {}, registro)
        alvo = [b["id"] for b in registro if b.get("workflow") and cfg["bots"][b["id"]]["ativo"]]
        n = {"c": 0}

        def fn(f):
            for b in alvo:
                if F.nova(f, b, agora, "executar", cfg["bots"][b]["prioridade"], "painel", cfg["bots"][b]["parametros"])[1]:
                    n["c"] += 1
            return f
        atualizar(store, FILA, fn, F.vazia, "core: executar todos")
        return f"{n['c']} tarefas criadas (uma por bot ativo, em sequência)"

    if acao == "cancelar_fila":
        n = {"c": 0}

        def fn(f):
            for t in f["tarefas"]:
                if t["estado"] in ("criada", "aguardando", "programada", "pausada") and F.cancelar(t, agora):
                    n["c"] += 1
            return f
        atualizar(store, FILA, fn, F.vazia, "core: cancelar fila")
        return f"{n['c']} tarefas em espera canceladas (as já iniciadas continuam)"

    if acao == "limpar":
        res = {}

        def fn(f):
            cfg = (store.ler(CFG)[0] or {}).get("global", {})
            res.update(F.limpar(f, agora, cfg.get("retencao_dias", 14)))
            return f
        atualizar(store, FILA, fn, F.vazia, "core: limpar")
        return f"{res['removidas']} tarefas antigas removidas"

    if acao in ("cancelar_tarefa", "cancelar_execucao", "pausar_tarefa", "retomar_tarefa"):
        res = {}

        def fn(f):
            t = tarefa(f)
            if acao == "cancelar_execucao":
                _exige(t["estado"] == "executando", "só dá para cancelar a execução de uma tarefa em andamento")
                t["cancelar_pedido"] = True
                F.log(t, "cancelamento pedido", agora)
                res["ok"] = True
            else:
                res["ok"] = {"cancelar_tarefa": F.cancelar, "pausar_tarefa": F.pausar, "retomar_tarefa": F.retomar}[acao](t, agora)
            return f
        atualizar(store, FILA, fn, F.vazia, f"core: {acao}")
        _exige(res["ok"], "essa tarefa não pode mudar assim no estado atual")
        return {"cancelar_execucao": "cancelamento pedido", "cancelar_tarefa": "tarefa cancelada", "pausar_tarefa": "tarefa pausada", "retomar_tarefa": "tarefa retomada"}[acao]

    if acao == "reprocessar":
        res = {}

        def fn(f):
            res["t"] = F.reprocessar(f, cmd.get("id"), agora)
            _exige(res["t"] is not None, "tarefa não está na dead-letter queue")
            return f
        atualizar(store, FILA, fn, F.vazia, "core: reprocessar")
        return f"tarefa reprocessada ({res['t']['id']})"

    if acao == "reiniciar_bot":
        bot = bot_valido()
        res = {}

        def fn(f):
            ativos = [t for t in f["tarefas"] if t["bot"] == bot]
            _exige(not any(t["estado"] == "executando" for t in ativos), "o bot está executando: cancele a execução antes de reiniciar")
            for t in ativos:
                F.cancelar(t, agora)
            res["t"], _ = F.nova(f, bot, agora, "executar", "alta", "painel")
            return f
        atualizar(store, FILA, fn, F.vazia, f"core: reiniciar {bot}")
        return f"{bot}: reiniciado (tarefa {res['t']['id']})"

    raise ErroComando(f"ação desconhecida: {acao}")


def _mesclar(c, registro):
    from .despachante import mesclar_config
    return mesclar_config(c, registro)


def _g(c, registro, campos):
    c = _mesclar(c, registro)
    c["global"].update(campos)
    return c
