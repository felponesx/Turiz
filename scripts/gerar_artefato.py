#!/usr/bin/env python3
"""Gera a versão "artefato" do painel (visualização somente leitura com um retrato dos dados reais).
O artefato do claude.ai não pode buscar dados no GitHub (CSP), então o retrato vai junto como arquivos JSON.
Saída: PASTA/index.html + PASTA/d/*.json (status e dados) + PASTA/c/*.json (Core). Uso: python scripts/gerar_artefato.py PASTA"""
import gzip
import json
import os
import re
import sys
import urllib.request

REPO = "felponesx/Turiz"
RAW = f"https://raw.githubusercontent.com/{REPO}"


def baixar(branch, caminho):
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{RAW}/{branch}/{caminho}", headers={"User-Agent": "turiz-artefato"}), timeout=60) as r:
            return r.read()
    except Exception:  # noqa: BLE001
        return None


def main(saida):
    os.makedirs(f"{saida}/d", exist_ok=True)
    os.makedirs(f"{saida}/c", exist_ok=True)
    reg = json.load(open("painel/bots.json", encoding="utf-8"))
    n = 0
    for b in reg["bots"]:
        raw = baixar("bot-status", f"status/{b['id']}.json")
        if raw:
            open(f"{saida}/d/{b['id']}.json", "wb").write(raw); n += 1
    for nome in ("bots", "fila", "resumo", "config"):
        raw = baixar("bot-control", f"control/{nome}.json")
        if raw:
            open(f"{saida}/c/{nome}.json", "wb").write(raw)
    for nome in ("coverage_summary.json", "revisao_resumo.json"):
        open(f"{saida}/d/{nome}", "wb").write(open(f"data/{nome}", "rb").read())
    for nome in ("coverage_neighborhoods", "coverage_metrics", "coverage_categories", "coverage_priorities", "coverage_history", "descobertas"):
        p = f"data/{nome}.json.gz"
        if os.path.exists(p):
            open(f"{saida}/d/{nome}.json", "wb").write(gzip.open(p, "rb").read())
    js = open("painel/app.js", encoding="utf-8").read()
    js = js.replace('const PARAMS = new URLSearchParams(location.search);', 'const PARAMS = new URLSearchParams("base=d/&ctl=c/");\nconst SOMENTE_LEITURA = true;\nlet HASH_ATUAL = "#/";\nconst navegar = (h) => { HASH_ATUAL = h; window.scrollTo(0, 0); desenhar(); };', 1)
    js = re.sub(r'location\.hash = ([^;]+?);', r'navegar(\1);', js)
    js = js.replace('location.hash.replace(', 'HASH_ATUAL.replace(')
    js = js.replace('window.addEventListener("hashchange", () => { window.scrollTo(0, 0); desenhar(); if (!["ajustes"].includes(rota().tela)) atualizar(); });',
                    'document.addEventListener("click", (e) => { const a = e.target.closest && e.target.closest(\'a[href^="#/"]\'); if (a) { e.preventDefault(); navegar(a.getAttribute("href")); } });')
    js = js.replace('async function comando(obj, opts = {}) {', 'async function comando(obj, opts = {}) {\n  if (SOMENTE_LEITURA) { aviso("Esta é a versão para visualizar. Para comandar os bots, use o painel instalado no celular."); return false; }', 1)
    js = js.replace('  if (base) url = base + caminho.split("/").pop();\n  else if (cfg.token) { url = `https://api.github.com/repos/${cfg.repo}/contents/${caminho}?ref=${cfg.dados}`; init.headers = { Authorization: `Bearer ${cfg.token}`, Accept: "application/vnd.github.raw+json" }; }\n  else url = `https://raw.githubusercontent.com/${cfg.repo}/${cfg.dados}/${caminho}?t=${Date.now()}`;\n  const r = await fetch(url, init);\n  if (r.status === 404) return null;\n  if (!r.ok) throw new Error("HTTP " + r.status);\n  if (typeof DecompressionStream',
                    '  if (base) { const r0 = await fetch(base + caminho.split("/").pop().replace(/\\.gz$/, ""), init); if (r0.status === 404) return null; if (!r0.ok) throw new Error("HTTP " + r0.status); return r0.json(); }\n  if (cfg.token) { url = `https://api.github.com/repos/${cfg.repo}/contents/${caminho}?ref=${cfg.dados}`; init.headers = { Authorization: `Bearer ${cfg.token}`, Accept: "application/vnd.github.raw+json" }; }\n  else url = `https://raw.githubusercontent.com/${cfg.repo}/${cfg.dados}/${caminho}?t=${Date.now()}`;\n  const r = await fetch(url, init);\n  if (r.status === 404) return null;\n  if (!r.ok) throw new Error("HTTP " + r.status);\n  if (typeof DecompressionStream', 1)
    js = re.sub(r'if \("serviceWorker" in navigator[^\n]*\n', '', js)
    js = js.replace("</script", "<\\/script")
    bots = "window.BOTS_REGISTRY = " + json.dumps(reg, ensure_ascii=False) + ";"
    css = open("painel/estilo.css", encoding="utf-8").read()
    idx = open("painel/index.html", encoding="utf-8").read()
    corpo = re.search(r"<body>(.*)</body>", idx, re.S).group(1)
    corpo = re.sub(r'<script src="[^"]+"></script>', "", corpo)
    corpo = corpo.replace('href="#/"', 'href="#/"')
    snap = json.load(open(f"{saida}/d/geo_scanner.json")) if os.path.exists(f"{saida}/d/geo_scanner.json") else {}
    pagina = f'''<title>Turiz Bot Control</title>
<meta name="description" content="Painel dos bots do TURIZ (retrato dos dados reais)">
<meta name="claude:viewport-fit-sides" content="cover">
<style>
html,body{{background:#121212;color:#ecebe8;margin:0}}
{css}
.faixa-retrato{{background:#2b2412;color:#e5b35c;font-size:.78rem;padding:6px 16px;text-align:center}}
</style>
<div class="faixa-retrato">Retrato dos dados em <span id="retrato-quando"></span> · só visualização</div>
{corpo}
<script>{bots}</script>
<script>document.getElementById("retrato-quando").textContent = new Date().toLocaleString("pt-BR", {{timeZone: "America/Sao_Paulo"}}).slice(0, 16);</script>
<script>
{js}
</script>
'''
    open(f"{saida}/index.html", "w", encoding="utf-8").write(pagina)
    print(f"{n} status, página de {len(pagina)//1024} KB")


if __name__ == "__main__":
    main(sys.argv[1])
