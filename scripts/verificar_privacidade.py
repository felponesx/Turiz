#!/usr/bin/env python3
"""Varredura de privacidade dos dados versionados: nenhum CNPJ, CPF ou e-mail pode estar no repositório (regra do projeto).
Procura em data/*.json e data/*.json.gz (todos os campos, exceto identificadores técnicos 'fonte_id'/'id'/'url' que são hashes/links).
Sai com código 1 se achar algo, e NUNCA imprime o valor encontrado (só arquivo, campo e tipo), para não vazar o dado no log do CI."""
import glob
import gzip
import json
import re
import sys

CNPJ = re.compile(r"(?<!\d)\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}(?!\d)")
CNPJ_CRU = re.compile(r"(?<![\d.])\d{14}(?![\d])")
CPF = re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}")
IGNORAR = {"fonte_id", "id", "lugar_fonte_id", "url", "thumb_url", "creditos_url", "ingresso_url", "imagem_url", "hash_nota", "hash_emitente", "pagina", "arquivo"}


SO_PONTUADO = {"site"}      # URLs podem ter ids numéricos longos (ex.: loja 12345678901234): nelas só vale o CNPJ pontuado


def varrer(obj, caminho, achados, arq, campo=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in IGNORAR:
                continue
            varrer(v, f"{caminho}.{k}" if caminho else k, achados, arq, k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            varrer(v, f"{caminho}[]", achados, arq, campo)
    elif isinstance(obj, str):
        for tipo, rx in (("CNPJ", CNPJ), ("CNPJ(14 dígitos)", CNPJ_CRU), ("CPF", CPF), ("e-mail", EMAIL)):
            if tipo == "CNPJ(14 dígitos)" and campo in SO_PONTUADO:
                continue
            if rx.search(obj):
                achados.append((arq, caminho, tipo))


def main(padroes=("data/*.json", "data/*.json.gz")):
    achados, arquivos = [], 0
    for padrao in padroes:
        for arq in sorted(glob.glob(padrao)):
            arquivos += 1
            abrir = gzip.open if arq.endswith(".gz") else open
            try:
                with abrir(arq, "rt", encoding="utf-8") as f:
                    dados = json.load(f)
            except Exception as exc:                          # arquivo ilegível também é problema
                achados.append((arq, "-", f"ilegível: {type(exc).__name__}"))
                continue
            varrer(dados, "", achados, arq)
    resumo = {}
    for arq, campo, tipo in achados:
        resumo[(arq, campo, tipo)] = resumo.get((arq, campo, tipo), 0) + 1
    for (arq, campo, tipo), n in resumo.items():
        print(f"ACHADO {tipo} em {arq} campo={campo} ocorrências={n}")
    print(f"varredura de privacidade: {arquivos} arquivos, {len(achados)} ocorrências")
    return 1 if achados else 0


if __name__ == "__main__":
    sys.exit(main())
