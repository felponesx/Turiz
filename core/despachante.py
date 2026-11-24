"""Despachante: um ciclo do TURIZ Core (roda a cada ~10 min no GitHub Actions e quando o painel pede).

Um ciclo: (1) reconcilia tarefas em execução com o GitHub; (2) expira o que ficou velho na fila; (3) agenda o que está devido;
(4) dispara as próximas tarefas respeitando pausa, concorrência e dependências; (5) publica o resumo para o painel.
Efeitos externos (disparar/cancelar execuções) acontecem DEPOIS de a tarefa ser reservada na fila (no máximo uma vez)."""
import argparse
import json
import os
import random
import sys
from datetime import datetime, timedelta

from . import agenda, fila as F
from .lancador import Lancador
from .modelos import agora_utc, config_bot_padrao, config_global_padrao, iso, parse
from .store import ArquivoStore, GitHubStore, atualizar

CFG, FILA, BOTS, RESUMO = "control/config.json", "control/fila.json", "control/bots.json", "control/resumo.json"
SEM_RUN_MIN = 30             # tarefa "executando" sem execução correspondente no GitHub por mais que isso => falha
BATIMENTO = timedelta(minutes=30)


# ---------- configuração ----------
def mesclar_config(cfg: dict | None, registro: list[dict]) -> dict:
    """Garante configuração para todo bot do registro (bot novo aparece sozinho) e preserva o que o usuário já definiu."""
    cfg = cfg or {}
    g = {**config_global_padrao(), **cfg.get("global", {})}
    g["retry"] = {**config_global_padrao()["retry"], **g.get("retry", {})}
    bots = dict(cfg.get("bots", {}))
    for b in registro:
        antigo = bots.get(b["id"], {})
        bots[b["id"]] = {**config_bot_padrao(b), **antigo, "limites": {**config_bot_padrao(b)["limites"], **antigo.get("limites", {})}}
    return {"global": g, "bots": bots}


def workflows_de_dados(registro) -> set[str]:
    return {b["workflow"] for b in registro if b.get("workflow")} | {"coleta.yml"}


# ---------- reconciliação ----------
def _classificar(status: dict | None):
    """Interpreta o status final publicado pelo bot -> (estado_da_tarefa, contagens, resultado)."""
    if not status:
        return "concluida", {}, None
    c = status.get("contagem", {}) or {}
    cont = {k: c.get(k, 0) for k in F.CONTAGENS}
    cont["rejeitados"] = cont.get("rejeitados") or (c.get("falhas", 0) + c.get("bloqueados", 0))
    est = status.get("estado")
    if est == "erro":
        return "falhou", cont, status.get("mensagem")
    if est in ("avisos", "aguardando_credencial", "aguardando_config", "pausado"):
        return "concluida_parcial", cont, status.get("mensagem") or est
    return "concluida", cont, status.get("mensagem") or None


def _reconciliar(fila, cfg, agora, estados, achados, ler_status, rng, ack):
    for t in [x for x in fila["tarefas"] if x["estado"] == "executando"]:
        rid = t.get("run_id") or achados.get(t["id"])
        if rid and not t.get("run_id"):
            t["run_id"] = rid
        decorrido = (agora - parse(t["iniciada_em"])).total_seconds() / 60
        st = estados.get(rid) if rid else None
        if t.get("cancelar_pedido"):                 # pedido do painel: cancela a execução no GitHub e fecha a tarefa
            if rid:
                ack["cancelar"].append(rid)
            F.cancelar(t, agora)
            continue
        limite = cfg["bots"].get(t["bot"], {}).get("limites", {}).get("max_minutos", 180)
        if st == "sucesso":
            res, cont, msg = _classificar(ler_status(t["bot"]))
            if res == "falhou":
                if F.falhar(fila, t, msg or "o bot terminou com erro", agora, cfg["global"]["retry"], rng) == "dlq":
                    ack["falhas"].append(t["id"])
            else:
                F.concluir(t, agora, cont, parcial=(res == "concluida_parcial"), resultado=msg)
                ack["concluidas"].append(t["id"])
        elif st == "cancelado":
            F.cancelar(t, agora)
        elif st in ("falha", "desconhecido"):
            if F.falhar(fila, t, "a execução no GitHub falhou" if st == "falha" else "execução não encontrada", agora, cfg["global"]["retry"], rng) == "dlq":
                ack["falhas"].append(t["id"])
        elif st == "em_andamento" and decorrido > limite * 1.5:
            ack["cancelar"].append(rid)
            F.falhar(fila, t, f"tempo esgotado (> {int(limite * 1.5)} min)", agora, cfg["global"]["retry"], rng)
        elif not rid and decorrido > SEM_RUN_MIN:
            F.falhar(fila, t, "nenhuma execução correspondente no GitHub", agora, cfg["global"]["retry"], rng)


# ---------- agendamento ----------
def _agendar(fila, cfg, agora):
    novas = []
    meta, g = fila["meta"], cfg["global"]
    if g["pausado"]:
        return novas
    for bot, c in cfg["bots"].items():
        if not (c["ativo"] and c["gerenciado"]):
            continue
        ag = c["agenda"]
        if ag.get("tipo") == "apos":
            for dep in ag.get("bots", []):
                chave = f"{bot}<-{dep}"
                visto = meta["apos_visto"].get(chave, "")
                fins = [t for t in fila["tarefas"] if t["bot"] == dep and t["estado"] in ("concluida", "concluida_parcial") and (t["finalizada_em"] or "") > visto]
                if fins:
                    meta["apos_visto"][chave] = max(t["finalizada_em"] for t in fins)
                    t, criada = F.nova(fila, bot, agora, prioridade=c["prioridade"], origem="dependencia", parametros=c["parametros"], max_tentativas=c["max_tentativas"])
                    if criada:
                        novas.append(t["id"])
            continue
        ultimo = parse(meta["ultimo_agendado"].get(bot))
        devida, oc = agenda.avaliar(ag, agora, ultimo, g["timezone"])
        if oc and (ultimo is None or oc > ultimo):
            meta["ultimo_agendado"][bot] = iso(oc)
        if devida:
            t, criada = F.nova(fila, bot, agora, prioridade=c["prioridade"], origem="agenda", parametros=c["parametros"], max_tentativas=c["max_tentativas"])
            if criada:
                novas.append(t["id"])
    return novas


def _bloqueados(fila, cfg):
    """Bots que não devem iniciar agora: desligados, ou esperando outro bot (depende_de) que ainda tem tarefa ativa."""
    ativos = {t["bot"] for t in fila["tarefas"] if t["estado"] in ("executando", "aguardando", "programada", "criada")}
    bloq = {b for b, c in cfg["bots"].items() if not c["ativo"]}
    for b, c in cfg["bots"].items():
        if any(d in ativos for d in c.get("depende_de", [])):
            bloq.add(b)
    return bloq


# ---------- ciclo ----------
def ciclo(store, lancador, registro, agora: datetime, rng=random, ler_status=lambda bot: None) -> dict:
    por_id = {b["id"]: b for b in registro}
    cfg = atualizar(store, CFG, lambda d: mesclar_config(d, registro), lambda: {}, "core: configuração")
    ack = {"concluidas": [], "falhas": [], "cancelar": [], "agendadas": [], "iniciadas": [], "externos": []}

    # leituras externas (fora da região de retry de conflito)
    atual, _ = store.ler(FILA)
    executando = [t for t in (atual or F.vazia())["tarefas"] if t["estado"] == "executando"]
    estados, achados = {}, {}
    if lancador:
        for t in executando:
            try:
                if t.get("run_id"):
                    estados[t["run_id"]] = lancador.estado(t["run_id"])[0]
                else:
                    rid = lancador.achar_execucao(por_id.get(t["bot"], {}).get("workflow") or "", t["iniciada_em"])
                    if rid:
                        achados[t["id"]] = rid
                        estados[rid] = lancador.estado(rid)[0]
            except Exception:  # noqa: BLE001 - falha de rede não derruba o ciclo
                pass
        try:
            ack["externos"] = lancador.ocupado(workflows_de_dados(registro), {t["run_id"] for t in executando if t.get("run_id")})
        except Exception:  # noqa: BLE001
            ack["externos"] = ["desconhecido"]

    reservadas = []

    def passo(fila):
        reservadas.clear()
        ack["concluidas"].clear(), ack["falhas"].clear(), ack["cancelar"].clear(), ack["agendadas"].clear()
        g = cfg["global"]
        _reconciliar(fila, cfg, agora, estados, achados, ler_status, rng, ack)
        F.expirar(fila, agora, g["ttl_espera_horas"])
        ack["agendadas"].extend(_agendar(fila, cfg, agora))
        F.limpar(fila, agora, g["retencao_dias"])
        em_exec = sum(1 for t in fila["tarefas"] if t["estado"] == "executando")
        vagas = 0 if (g["pausado"] or lancador is None or ack["externos"]) else max(0, g["max_concorrencia"] - em_exec)
        for t in F.proximas(fila, agora, vagas, _bloqueados(fila, cfg)):
            F.iniciar(t, agora)          # reserva antes de disparar: nunca dispara duas vezes a mesma tarefa
            reservadas.append(t["id"])
        ult = parse(fila["meta"].get("ultimo_ciclo"))
        if ult is None or agora - ult >= BATIMENTO:      # o batimento só é gravado de tempos em tempos (evita um commit a cada ciclo)
            fila["meta"]["ultimo_ciclo"] = iso(agora)
        return fila

    fila = atualizar(store, FILA, passo, F.vazia, "core: ciclo")

    # efeitos externos
    if lancador:
        for rid in ack["cancelar"]:
            try:
                lancador.cancelar(rid)
            except Exception:  # noqa: BLE001
                pass
    resultados = {}
    for tid in list(reservadas):
        t = next(x for x in fila["tarefas"] if x["id"] == tid)
        meta = por_id.get(t["bot"], {})
        try:
            if not meta.get("workflow"):
                raise RuntimeError("bot sem workflow para disparar")
            entradas = dict(meta.get("entradas", {}))
            if meta.get("encadeia"):
                entradas["encadear"] = "false"      # tarefa do Core não deve disparar a cadeia antiga
            resultados[tid] = ("ok", lancador.disparar(meta["workflow"], entradas))
            ack["iniciadas"].append(tid)
        except Exception as exc:  # noqa: BLE001
            resultados[tid] = ("erro", str(exc))
    if resultados:
        def registrar(f):
            for tid, (res, val) in resultados.items():
                t = next((x for x in f["tarefas"] if x["id"] == tid), None)
                if not t or t["estado"] != "executando":
                    continue
                if res == "ok":
                    t["run_id"] = val
                    F.log(t, f"execução {val}" if val else "disparada (execução ainda não identificada)", agora)
                else:
                    F.falhar(f, t, val, agora, cfg["global"]["retry"], rng)
            return f
        fila = atualizar(store, FILA, registrar, F.vazia, "core: execuções")

    publicar(store, cfg, fila, registro, agora, ack["externos"])
    return {k: v for k, v in ack.items() if v} | {"na_fila": F.resumo(fila)["na_fila"], "executando": F.resumo(fila)["executando"]}


# ---------- publicação para o painel ----------
def estatisticas(fila: dict, bot: str) -> dict:
    ts = [t for t in fila["tarefas"] + fila["dlq"] if t["bot"] == bot and t["estado"] in ("concluida", "concluida_parcial", "falhou", "cancelada")]
    ok = [t for t in ts if t["estado"] in ("concluida", "concluida_parcial")]
    dur = [t["duracao_s"] for t in ok if t.get("duracao_s")]
    soma = {k: sum(t["contagens"].get(k, 0) for t in ok) for k in F.CONTAGENS}
    ult = max(ts, key=lambda t: t["finalizada_em"] or "", default=None)
    return {"execucoes": len(ts), "sucessos": len(ok), "falhas": sum(1 for t in ts if t["estado"] == "falhou"), "duracao_media_s": int(sum(dur) / len(dur)) if dur else None,
            "contagens": soma, "ultima": {"estado": ult["estado"], "finalizada_em": ult["finalizada_em"], "erro": ult["erro"]} if ult else None}


def publicar(store, cfg, fila, registro, agora, externos):
    tz = cfg["global"]["timezone"]
    lista = []
    for b in registro:
        c = cfg["bots"][b["id"]]
        ultimo = parse(fila["meta"]["ultimo_agendado"].get(b["id"]))
        prox = agenda.proxima(c["agenda"], agora, ultimo, tz) if (c["ativo"] and c["gerenciado"]) else None
        pub = {k: v for k, v in b.items() if k not in ("saidas",)}
        lista.append({**pub, "config": c, "agenda_texto": agenda.descrever(c["agenda"]), "proxima_execucao": iso(prox) if prox else None,
                      "ativas": sum(1 for t in fila["tarefas"] if t["bot"] == b["id"] and t["estado"] in ("executando", "aguardando", "programada")),
                      "estatisticas": estatisticas(fila, b["id"])})
    atualizar(store, BOTS, lambda d: _estavel(d, {"gerado_em": iso(agora), "timezone": tz, "bots": lista}, agora), lambda: {}, "core: bots")
    atualizar(store, RESUMO, lambda d: _estavel(d, {"gerado_em": iso(agora), "global": cfg["global"], "fila": F.resumo(fila), "externos_ocupados": externos,
                                                    "ultimo_ciclo": fila["meta"]["ultimo_ciclo"]}, agora), lambda: {}, "core: resumo")


def _estavel(antigo: dict, novo: dict, agora: datetime) -> dict:
    """Mantém o arquivo como está se só o carimbo de tempo mudou (e há menos de 30 min): evita commit a cada ciclo."""
    if antigo and {k: v for k, v in antigo.items() if k != "gerado_em"} == {k: v for k, v in novo.items() if k != "gerado_em"}:
        g = parse(antigo.get("gerado_em"))
        if g and agora - g < BATIMENTO:
            return antigo
    return novo


# ---------- linha de comando ----------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Um ciclo do TURIZ Core")
    ap.add_argument("--local", help="pasta com os arquivos de controle (teste/simulação, sem GitHub)")
    ap.add_argument("--comando", help="comando do painel em JSON (padrão: variável TURIZ_COMANDO)")
    a = ap.parse_args(argv)
    from bots import registry
    registro = registry.BOTS
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY") or "felponesx/Turiz"
    if a.local:
        store, lanc, ler = ArquivoStore(a.local), None, (lambda bot: None)
    else:
        if not token:
            print("ERRO: sem GITHUB_TOKEN")
            return 2
        store, lanc = GitHubStore(repo, token), Lancador(repo, token)
        leitor = GitHubStore(repo, token, branch="bot-status")
        ler = lambda bot: (leitor.ler(f"status/{bot}.json") or (None,))[0]   # noqa: E731
    agora, codigo = agora_utc(), 0
    bruto = (a.comando if a.comando is not None else os.getenv("TURIZ_COMANDO", "")).strip()
    if bruto:
        from .comandos import ErroComando, aplicar
        try:
            msg = aplicar(store, json.loads(bruto), registro, agora)
            print("comando:", msg)
            _registrar_comando(store, True, msg, agora)
        except (ErroComando, ValueError) as exc:
            print("comando REJEITADO:", exc)
            _registrar_comando(store, False, str(exc), agora)
            codigo = 2
    r = ciclo(store, lanc, registro, agora, ler_status=ler)      # aplica o efeito já neste ciclo (ex.: iniciar a tarefa pedida)
    print("ciclo:", r)
    return codigo


def _registrar_comando(store, ok: bool, msg: str, agora):
    def fn(f):
        f["meta"]["ultimo_comando"] = {"ok": ok, "mensagem": msg[:300], "em": iso(agora)}
        return f
    atualizar(store, FILA, fn, F.vazia, "core: resultado do comando")


if __name__ == "__main__":
    sys.exit(main())
