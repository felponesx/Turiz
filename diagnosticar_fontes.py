#!/usr/bin/env python3
"""Testa as fontes candidatas e gera data/diagnostico_fontes.json + FONTES.md. Ex.: python diagnosticar_fontes.py"""
from datetime import datetime, timezone
from app.sources import diagnostico


def main():
    quando = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    res = diagnostico.diagnosticar()
    diagnostico.salvar(res, quando)
    cont = {}
    for r in res:
        cont[r["resultado"]] = cont.get(r["resultado"], 0) + 1
    for r in res:
        print(f"{r['id']:<22} {r['resultado']:<30} HTTP {r.get('status')}  eventos_jsonld={r.get('jsonld_eventos', '-')}")
    print("resumo:", cont)


if __name__ == "__main__":
    main()
