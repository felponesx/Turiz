#!/usr/bin/env python3
"""Geo Scanner: pesquisa no OpenStreetMap os distritos/categorias mais prioritários da cobertura geográfica.
Ex.: python coletar_geo.py [--max-tarefas 6] [--distrito 35 --categoria padaria]
Grava só data/descobertas.json.gz e o histórico de buscas (coverage_history). Não altera lugares.json."""
import argparse
import os

from app.sources import osm
from bots.status import bot
from cobertura.categorias import config
from geoscanner import scanner

DADOS = os.environ.get("TURIZ_DADOS", "data")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-tarefas", type=int, default=None)
    ap.add_argument("--distrito", default=None)
    ap.add_argument("--categoria", default=None)
    ap.add_argument("--max-minutos", type=float, default=60)
    a = ap.parse_args()
    with bot("geo_scanner") as rep:
        rep.progresso(0, 0, atual="Escolhendo distritos e categorias pela fila de prioridades")
        res = scanner.executar(DADOS, config("cobertura_config.yml"), lambda q: osm._post(q, tentativas=3, timeout=150), max_tarefas=a.max_tarefas,
                               distrito=a.distrito or None, categoria=a.categoria or None, rep=rep, max_minutos=a.max_minutos)
        rep.definir(descobertas=res["descobertas_total"], buscas_feitas=res["feitas"], falhas=res["falhas"])
        if not res["tarefas"]:
            rep.aviso("Nada a pesquisar agora: todas as buscas prioritárias são recentes (intervalo adaptativo).")
        print(res)


if __name__ == "__main__":
    main()
