#!/usr/bin/env python3
"""TURIZ Cobertura Geográfica (Fase 5): lê data/*.json, associa lugares a distritos oficiais, calcula cobertura, diversidade e prioridades.
Só gera inteligência e recomendações: NÃO dispara scanners e NÃO altera lugares.json nem os scores da Fase 4.
Ex.: python coletar_cobertura.py   (idempotente; ~15 s)"""
from bots.status import bot
from cobertura.rodar import DADOS, rodar


def main():
    with bot("cobertura") as rep:
        rodar(rep)


if __name__ == "__main__":
    main()
