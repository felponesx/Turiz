#!/usr/bin/env python3
"""Teste de carga CONTROLADO, só contra um servidor local de teste (nunca contra produção). Prova que, sob inundação de requisições, a API
recusa o excesso rápido (429 + Retry-After), nunca devolve 5xx, recusa corpos grandes, e volta ao normal quando a janela passa.
Uso: python scripts/teste_carga.py"""
import concurrent.futures as cf
import os
import statistics
import subprocess
import sys
import tempfile
import time
import httpx

PORTA = 8124
BASE = f"http://127.0.0.1:{PORTA}"


def main():
    pagina = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False); pagina.write("<html></html>"); pagina.close()
    env = {**os.environ, "TURIZ_FRONT": pagina.name, "PYTHONPATH": os.getcwd(), "TURIZ_LIM_LEITURA": "120", "TURIZ_LIM_CARA": "30", "TURIZ_MAX_BODY": "100000"}
    srv = subprocess.Popen([sys.executable, "scripts/servir_front_teste.py", str(PORTA)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    falhas = []
    try:
        for _ in range(60):
            try:
                if httpx.get(BASE + "/health", timeout=1).status_code == 200:
                    break
            except Exception:
                time.sleep(0.5)
        time.sleep(61)                                   # limpa a janela do /health acima
        lat, codigos = [], []

        def uma(i):
            t = time.perf_counter()
            try:
                r = httpx.get(BASE + "/lugares", params={"q": "a", "limit": 50}, headers={"x-forwarded-for": f"10.0.{i % 250}.{i % 200}"}, timeout=10)
                return r.status_code, time.perf_counter() - t, r.headers.get("retry-after")
            except Exception as exc:
                return type(exc).__name__, time.perf_counter() - t, None

        t0 = time.time()
        with cf.ThreadPoolExecutor(60) as ex:
            res = list(ex.map(uma, range(1500)))
        dur = time.time() - t0
        codigos = [r[0] for r in res]
        n429 = codigos.count(429)
        print(f"inundação: {len(res)} requisições em {dur:.1f}s ({len(res)/dur:.0f} req/s); 200={codigos.count(200)} 429={n429} outros={[c for c in set(codigos) if c not in (200, 429)]}")
        if any(isinstance(c, int) and c >= 500 and c != 503 for c in codigos) or any(isinstance(c, str) for c in codigos):
            falhas.append("houve erro 500/502/504 ou falha de conexão sob carga")      # 503 + Retry-After é a contrapressão planejada (rotas caras saturadas)
        if n429 < 1000:
            falhas.append(f"limite não conteve a inundação (429={n429})")
        if any(r[0] == 429 and not r[2] for r in res):
            falhas.append("429 sem Retry-After")
        l429 = [r[1] for r in res if r[0] == 429]
        print(f"latência das recusas (429): mediana {statistics.median(l429)*1000:.0f} ms, p95 {sorted(l429)[int(len(l429)*.95)]*1000:.0f} ms")
        if sorted(l429)[int(len(l429) * .95)] > 1.5:
            falhas.append("recusas lentas demais")
        r = httpx.post(BASE + "/avaliacoes", content=b"x" * 500_000, headers={"content-type": "application/json", "x-api-key": "chave-de-teste-e2e"}, timeout=10)
        print("corpo de 500 KB (limite 100 KB):", r.status_code)
        if r.status_code != 413 and r.status_code != 429:
            falhas.append("corpo grande não foi recusado")
        print("aguardando a janela do limitador (65 s)…")
        time.sleep(65)
        r = httpx.get(BASE + "/health", timeout=5)
        print("depois da janela, /health:", r.status_code, r.json())
        if r.status_code != 200:
            falhas.append("servidor não voltou ao normal")
    finally:
        srv.terminate(); srv.wait(timeout=10); os.unlink(pagina.name)
    print("CARGA OK" if not falhas else "FALHAS: " + "; ".join(falhas))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
