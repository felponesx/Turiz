#!/usr/bin/env python3
"""Atualiza os DADOS embutidos na página do app Turiz (lugares, imagens, redes, cardápios, fotos, eventos) com o que os bots captaram.

  python scripts/atualizar_app_turiz.py <pagina_atual.html> <pagina_nova.html> [--dados data]

Só troca os blocos <!--API-...--> (o resto da página, visual e código, fica idêntico). Códigos de saída:
  0 = página nova gerada e DIFERENTE da atual (publicar)    3 = nada mudou (não precisa publicar)    2 = falhou uma verificação (NÃO publicar)
Imprime linhas `chave=valor` com os totais, para o relatório do painel."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

LIMITE_BYTES = 15 * 1024 * 1024          # o Artifact aceita até 16 MB
BLOCOS = ["API-DATA", "API-IMAGENS", "API-REDES", "API-CARDAPIOS", "API-EVENTOS", "API-FOTOS-EX"]
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def blocos(html):
    out = {}
    for nome in BLOCOS:
        m = re.search(rf"<!--{nome}-->(.*?)<!--/{nome}-->", html, re.S)
        if m:
            out[nome] = m.group(1)
    return out


def contar(html):
    """Totais lidos dos blocos JSON embutidos (confere que o resultado é um JSON válido)."""
    t = {}
    for ident, chave in (("api-lugares", "lugares"), ("api-imagens", "lugares_com_imagem"), ("api-redes", "lugares_com_rede"),
                         ("api-cardapios", "lugares_com_cardapio"), ("api-eventos", "eventos")):
        m = re.search(rf'<script type="application/json" id="{ident}">(.*?)</script>', html, re.S)
        if m:
            d = json.loads(m.group(1).replace("<\\/", "</"))
            t[chave] = len(d["itens"]) if isinstance(d, dict) and "itens" in d else len(d)
    return t


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("atual")
    ap.add_argument("nova")
    ap.add_argument("--dados", default=os.path.join(RAIZ, "data"))
    a = ap.parse_args(argv)
    try:
        import PIL.Image  # noqa: F401
        import yaml  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        print(f"ERRO: Python sem Pillow/PyYAML funcionando ({type(exc).__name__}). Rode `pip install -r requirements.txt` ou use /usr/bin/python3.")
        return 2
    antes = open(a.atual, encoding="utf-8").read()
    faltam = [b for b in ("API-DATA", "API-IMAGENS", "API-REDES") if f"<!--{b}-->" not in antes]
    if faltam:
        print("ERRO: a página não tem os blocos de dados esperados:", faltam)
        return 2
    shutil.copyfile(a.atual, a.nova)
    r = subprocess.run([sys.executable, os.path.join(RAIZ, "frontend", "build_api_all.py"), a.dados, a.nova], capture_output=True, text=True, cwd=RAIZ)
    if r.returncode != 0:
        print("ERRO no builder:", r.stderr[-600:])
        return 2
    depois = open(a.nova, encoding="utf-8").read()
    for linha in r.stdout.strip().splitlines():
        print("builder:", linha)
    if len(depois.encode("utf-8")) > LIMITE_BYTES:
        print(f"ERRO: página com {len(depois)//1024//1024} MB passa do limite do Artifact")
        return 2
    # o que NÃO é dado precisa ficar idêntico: remove os blocos e compara
    def sem_blocos(h):
        for n in BLOCOS:
            h = re.sub(rf"<!--{n}-->.*?<!--/{n}-->", "", h, flags=re.S)
        return re.sub(r"\s+", " ", h)
    if sem_blocos(antes) != sem_blocos(depois):
        print("ERRO: o builder mexeu em algo fora dos blocos de dados; não publicar")
        return 2
    try:
        tot = contar(depois)
    except (ValueError, KeyError) as exc:
        print("ERRO: bloco de dados inválido:", type(exc).__name__)
        return 2
    antes_t = contar(antes)
    for k, v in tot.items():
        print(f"{k}={v}")
        if antes_t.get(k, 0) > 0 and v < 0.5 * antes_t[k]:
            print(f"ERRO: {k} caiu de {antes_t[k]} para {v}; não publicar")
            return 2
    print(f"tamanho_mb={len(depois.encode('utf-8'))/1048576:.1f}")
    if depois == antes:
        print("sem_mudancas=1")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
