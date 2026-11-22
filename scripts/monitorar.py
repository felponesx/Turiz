#!/usr/bin/env python3
"""Monitor EXTERNO do TURIZ (roda no GitHub Actions, fora do app): disponibilidade, tempo de resposta, JSON do /health, cabeçalhos de
segurança, HTTPS e validade do certificado. Sai com código 1 e lista de problemas; o workflow abre um incidente.
Uso: python scripts/monitorar.py https://api.exemplo.com"""
import json
import socket
import ssl
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx

CABECALHOS_OBRIGATORIOS = ("x-content-type-options", "content-security-policy", "referrer-policy")
LIMITE_LENTO_S = 3.0
DIAS_CERTIFICADO_ALERTA = 14


def dias_do_certificado(host: str, porta: int = 443) -> int | None:
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, porta), timeout=10) as s, ctx.wrap_socket(s, server_hostname=host) as t:
            expira = datetime.strptime(t.getpeercert()["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        return (expira - datetime.now(timezone.utc)).days
    except Exception:
        return None


def verificar(url: str, client: httpx.Client | None = None, checar_certificado: bool = True) -> list[str]:
    problemas = []
    u = urlparse(url)
    if u.scheme != "https":
        problemas.append("URL não usa HTTPS")
    cli = client or httpx.Client(timeout=15, follow_redirects=False)
    for tentativa in range(3):                               # 3 tentativas: ruído de rede não vira incidente
        try:
            t0 = time.perf_counter()
            r = cli.get(url.rstrip("/") + "/health")
            seg = time.perf_counter() - t0
            break
        except httpx.HTTPError as exc:
            if tentativa == 2:
                return problemas + [f"fora do ar: {type(exc).__name__}"]
            time.sleep(2)
    if r.status_code != 200:
        problemas.append(f"/health respondeu HTTP {r.status_code}")
    else:
        try:
            if r.json().get("ok") is not True:
                problemas.append("/health não confirma ok=true")
        except ValueError:
            problemas.append("/health não devolveu JSON")
    if seg > LIMITE_LENTO_S:
        problemas.append(f"lento: {seg:.1f}s (limite {LIMITE_LENTO_S}s)")
    faltando = [h for h in CABECALHOS_OBRIGATORIOS if h not in {k.lower() for k in r.headers}]
    if faltando:
        problemas.append("cabeçalhos de segurança ausentes: " + ", ".join(faltando))
    if checar_certificado and u.scheme == "https" and u.hostname:
        dias = dias_do_certificado(u.hostname, u.port or 443)
        if dias is None:
            problemas.append("não foi possível validar o certificado TLS")
        elif dias < DIAS_CERTIFICADO_ALERTA:
            problemas.append(f"certificado expira em {dias} dias")
    docs = cli.get(url.rstrip("/") + "/docs")
    if docs.status_code == 200:
        problemas.append("/docs está público em produção")
    return problemas


if __name__ == "__main__":
    alvo = sys.argv[1]
    achados = verificar(alvo)
    print(json.dumps({"url": alvo, "ok": not achados, "problemas": achados}, ensure_ascii=False))
    sys.exit(1 if achados else 0)
