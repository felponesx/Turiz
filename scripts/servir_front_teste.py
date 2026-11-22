#!/usr/bin/env python3
"""Servidor de TESTE: a API real (banco temporário) + o front de produção em /turiz, na MESMA origem (cookies e CSRF reais).
Uso: TURIZ_FRONT=dist/turiz.prod.html python scripts/servir_front_teste.py 8123"""
import os
import sys
import tempfile

tmp = tempfile.mkdtemp(prefix="turiz-e2e-")
os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/e2e.db"
os.environ.setdefault("API_KEY", "chave-de-teste-e2e")
os.environ["TURIZ_EMAIL_BACKEND"] = "teste"
sys.path.insert(0, os.getcwd())

import uvicorn  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from app.main import app  # noqa: E402

CAMINHO = os.environ["TURIZ_FRONT"]
if os.path.exists(CAMINHO + ".csp.txt"):          # o servidor envia a MESMA CSP que o build gerou
    os.environ["TURIZ_CSP_PAGINA"] = open(CAMINHO + ".csp.txt").read().strip() + "; frame-ancestors 'none'"


async def front():
    return FileResponse(CAMINHO, media_type="text/html")


if os.getenv("TURIZ_E2E_TOTP"):                       # administrador de teste com MFA já configurado (segredo vem do teste)
    from app.conta import cripto
    from app.conta.cli import criar_usuario
    from app.db import SessionLocal
    with SessionLocal() as _db:
        _u = criar_usuario(_db, "admin.e2e@exemplo.com", "frase de admin bem longa 2026", "admin")
        _u.mfa_ativo, _u.mfa_segredo = True, cripto.cifrar(os.environ["TURIZ_E2E_TOTP"])
        _db.commit()

app.add_api_route("/turiz", front, include_in_schema=False)
app.router.routes.insert(0, app.router.routes.pop())          # antes do mount estático

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]), log_level="warning", proxy_headers=False)   # o app decide em quem confiar (TURIZ_PROXY_HOPS)
