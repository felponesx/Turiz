#!/usr/bin/env python3
"""Testa uma ou mais URLs como fonte de eventos/lugares, sem gravar no banco.
Ex.: python testar_fonte.py https://site.com/agenda
     python testar_fonte.py https://site.com/agenda --listagem --padrao '^/evento/' --limite 20
Gera data/teste_fonte.md com o resultado (usado pelo workflow 'Testar fonte')."""
import argparse
import tempfile
import httpx
import yaml
from datetime import datetime, timezone
from app.sources import diagnostico, sites


def testar_url(url, listagem, padrao, limite, tipo, cidade=""):
    client = httpx.Client(timeout=30, headers={"User-Agent": sites.UA}, follow_redirects=True)
    diag = diagnostico.testar({"id": url, "categoria": "evento", "tipo": "html", "url": url}, client)
    linhas = [f"## {url}", "", f"- Resultado: **{diag['resultado']}** (HTTP {diag.get('status')})",
              f"- robots.txt permite: {diag.get('robots_permite')}",
              f"- JSON-LD na página: {diag.get('jsonld_eventos', 0)} eventos, {diag.get('jsonld_lugares', 0)} lugares"]
    if diag.get("detalhes_testados"):
        linhas.append(f"- Páginas de evento sondadas: {diag['detalhes_com_evento']}/{diag['detalhes_testados']} com JSON-LD (ex.: {', '.join(diag.get('detalhes_exemplos', []))})")
    cfg = {"sites": [{"url": url, "tipo": tipo, "pausa": 2, **({"cidade": cidade} if cidade else {}),
                      **({"listagem": True, "padrao_link": padrao, "limite": limite} if listagem else {})}]}
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False, encoding="utf-8") as f:
        yaml.safe_dump(cfg, f)
    try:
        lugares, eventos, ignorados = sites.coletar(f.name, client=client)
    except Exception as exc:
        linhas += ["", f"Falha ao coletar: `{type(exc).__name__}: {exc}`"]
        return "\n".join(linhas) + "\n"
    linhas += [f"- **Coleta de teste: {len(eventos)} eventos, {len(lugares)} lugares** (ignorados por robots/erro: {len(ignorados)})", ""]
    if eventos:
        linhas += ["| Título | Início | Local | Preço | Categoria |", "|---|---|---|---|---|"]
        for e in eventos[:8]:
            ini = e["inicio"].strftime("%d/%m/%Y %H:%M") if e.get("inicio") else "-"
            preco = "gratuito" if e.get("gratuito") else (f"R$ {e['preco_min']:.2f}" if e.get("preco_min") is not None else "-")
            linhas.append(f"| {e['titulo'][:70]} | {ini} | {e.get('local_nome', '')[:40]} | {preco} | {e.get('categoria', '')} |")
    elif not listagem and diag.get("detalhes_com_evento"):
        linhas.append("Dica: a lista não tem JSON-LD, mas as páginas dos eventos têm. Rode de novo com `--listagem` e um `--padrao` para os links (ex.: `^/evento/`).")
    return "\n".join(linhas) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--listagem", action="store_true", help="a página é uma lista: seguir os links dos eventos")
    ap.add_argument("--padrao", default=r"/evento", help="regex do caminho dos links dos eventos (modo listagem)")
    ap.add_argument("--limite", type=int, default=15)
    ap.add_argument("--tipo", default="evento", choices=["evento", "restaurante", "bar"])
    ap.add_argument("--cidade", default="São Paulo", help="só mantém eventos desta cidade ('' = todas)")
    a = ap.parse_args()
    texto = f"# Teste de fonte\n\nGerado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} (UTC).\n\n"
    for u in a.urls:
        texto += testar_url(u, a.listagem, a.padrao, a.limite, a.tipo, a.cidade) + "\n"
    open("data/teste_fonte.md", "w", encoding="utf-8").write(texto)
    print(texto)


if __name__ == "__main__":
    main()
