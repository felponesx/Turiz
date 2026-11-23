"""Publica o status de um bot a partir de fora do Python do bot (ex.: a tarefa agendada que atualiza o app Turiz).

  python -m bots.cli turiz_app inicio --etapa "Lendo o app"
  python -m bots.cli turiz_app progresso 60 --atual "Embutindo eventos" --item "4.443 lugares"
  python -m bots.cli turiz_app fim concluido --mensagem "App atualizado" --total lugares=4443 --conta novos=3
Precisa de TURIZ_STATUS_PUBLICAR=1 e GITHUB_TOKEN/GH_TOKEN (sem isso só grava status/<id>.json local)."""
import argparse
import sys
from .status import Reporter, criar_publicador


def _pares(lista):
    saida = {}
    for p in lista or []:
        k, _, v = p.partition("=")
        saida[k.strip()] = int(v) if v.strip().lstrip("-").isdigit() else v.strip()
    return saida


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("bot")
    ap.add_argument("acao", choices=["inicio", "progresso", "fim"])
    ap.add_argument("valor", nargs="?", help="percentual (progresso) ou estado final (fim: concluido|avisos|erro|aguardando_credencial)")
    ap.add_argument("--atual")
    ap.add_argument("--etapa")
    ap.add_argument("--item", action="append")
    ap.add_argument("--mensagem", default="")
    ap.add_argument("--total", action="append", help="chave=valor (totais no sistema)")
    ap.add_argument("--conta", action="append", help="chave=valor (contagem)")
    a = ap.parse_args(argv)
    rep = Reporter(a.bot, criar_publicador())
    try:   # continua de onde o status parou (a CLI roda em processos separados)
        ant = rep.pub.ler(f"status/{a.bot}.json") if rep.pub else None
    except Exception:  # noqa: BLE001
        ant = None
    if ant and a.acao != "inicio":
        for k in ("estado", "percentual", "etapa", "atual", "feitos", "total", "contagem", "totais", "itens", "log", "avisos", "fontes", "historico", "iniciado_em", "ultimo_sucesso", "run_url"):
            if k in ant:
                setattr(rep, {"log": "log_"}.get(k, k), ant[k])
    elif ant:
        rep.historico, rep.ultimo_sucesso, rep.totais = ant.get("historico", []), ant.get("ultimo_sucesso", ""), ant.get("totais", {})
    rep.contagem.update(_pares(a.conta))
    rep.totais.update(_pares(a.total))
    for i in a.item or []:
        rep.item(i)
    if a.acao == "inicio":
        rep.iniciar()
        rep.progresso(0, 0, atual=a.atual or "", etapa=a.etapa or "")
    elif a.acao == "progresso":
        rep.estado = "rodando"
        rep.percentual = max(rep.percentual, min(int(a.valor or 0), 99))
        rep.progresso(0, 0, atual=a.atual, etapa=a.etapa)
    else:
        rep.finalizar(a.valor or "concluido", a.mensagem)
    rep._salvar(forcar=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
