"""Injeção (SQL/NoSQL/cabeçalhos), CORS, sessões forjadas (não há JWT: sessões opacas) e abuso de entradas em TODAS as rotas GET públicas."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from app.db import SessionLocal
from app.main import app
from app.models import Lugar
from app.seguranca.modelos import Usuario

PAYLOADS = ["' OR '1'='1", "\"; DROP TABLE lugares; --", "1; SELECT pg_sleep(5)--", "%' UNION SELECT senha_hash FROM usuarios--", "\x00", "../../etc/passwd",
            "${jndi:ldap://x}", "{{7*7}}", "<script>alert(1)</script>", "A" * 5000, "🍽️" * 300, "%27%20OR%201%3D1", "'; WAITFOR DELAY '0:0:5'--"]
ROTAS_GET = [("/lugares", ["q", "bairro", "culinaria", "fonte", "tipo", "limit", "offset", "aberto_agora"]),
             ("/eventos", ["q", "categoria", "cidade", "estado", "pais", "data_de", "data_ate", "preco_max", "tipo_local", "local", "fonte", "ordem", "limit", "offset"]),
             ("/eventos/busca", ["q"]), ("/lugares/geo", ["tipo"])]


def test_nenhum_payload_de_injecao_causa_erro_500_nem_vaza(cliente):
    with SessionLocal() as db:
        antes = db.scalar(text("SELECT count(*) FROM lugares")); usuarios = db.scalar(text("SELECT count(*) FROM usuarios"))
    for rota, params in ROTAS_GET:
        for p in params:
            for pay in PAYLOADS:
                r = cliente.get(rota, params={p: pay})
                assert r.status_code < 500, (rota, p, pay[:30], r.status_code)
                corpo = r.text.lower()
                assert "traceback" not in corpo and "sqlalchemy" not in corpo and "senha_hash" not in corpo and "syntax error" not in corpo
    with SessionLocal() as db:                                        # nada foi apagado/alterado pelos payloads
        assert db.scalar(text("SELECT count(*) FROM lugares")) == antes and db.scalar(text("SELECT count(*) FROM usuarios")) == usuarios


def test_ids_de_caminho_com_lixo_nao_derrubam(cliente):
    for caminho in ("/lugares/abc", "/lugares/-1", "/lugares/99999999999999999999", "/lugares/1;DROP", "/eventos/abc", "/lugares/1/eventos?x=%00", "/conta/favoritos/lugar/../../x"):
        assert cliente.get(caminho).status_code < 500


def test_cabecalho_host_e_injecao_de_cabecalhos(cliente):
    r = cliente.get("/health", headers={"x-request-id": "x\r\nSet-Cookie: roubo=1", "user-agent": "<script>"})
    assert "set-cookie" not in r.headers and r.status_code == 200


def test_cors_nao_libera_origens_arbitrarias(cliente):
    r = cliente.get("/lugares", headers={"origin": "https://site-malicioso.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
    pre = cliente.options("/conta/login", headers={"origin": "https://site-malicioso.example", "access-control-request-method": "POST"})
    assert "access-control-allow-origin" not in {k.lower() for k in pre.headers}


def test_hosts_nao_permitidos_sao_recusados(monkeypatch):
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    from fastapi import FastAPI
    mini = FastAPI(); mini.add_middleware(TrustedHostMiddleware, allowed_hosts=["api.turiz.app"])
    mini.get("/x")(lambda: {"ok": 1})
    assert TestClient(mini, base_url="http://api.turiz.app").get("/x").status_code == 200
    assert TestClient(mini, base_url="http://evil.example").get("/x").status_code == 400


def test_sessoes_forjadas_adulteradas_e_algoritmo_none_sao_recusadas(cliente):
    falsos = ["", "null", "undefined", "a" * 43, "../../etc/passwd", "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIiwicm9sZSI6ImFkbWluIn0.",       # JWT com alg=none (o TURIZ nem usa JWT)
              "' OR 1=1--", "{\"usuario\":1}"]
    for t in falsos:
        assert cliente.get("/conta/eu", headers={"authorization": f"Bearer {t}"}).status_code == 401
        c2 = TestClient(app); c2.cookies.set("turiz_sessao", t)
        assert c2.get("/conta/eu").status_code == 401 and c2.get("/conta/admin/resumo").status_code == 401


def test_csrf_forjado_e_requisicao_cruzada_sao_bloqueados():
    c = TestClient(app)
    assert c.post("/conta/cadastro", json={"email": "csrf2@exemplo.com", "senha": "uma frase bem longa 2026"}).status_code == 202
    r = c.post("/conta/login", json={"email": "csrf2@exemplo.com", "senha": "uma frase bem longa 2026"})
    assert r.status_code == 200
    # formulário em site malicioso: o navegador envia o cookie, mas NÃO consegue ler o token CSRF
    assert c.post("/conta/logout-todos", headers={"origin": "https://site-malicioso.example"}).status_code == 403
    assert c.post("/conta/logout-todos").status_code == 403
    assert c.post("/conta/logout-todos", headers={"x-csrf-token": r.json()["csrf"][::-1]}).status_code == 403
    assert c.post("/conta/logout-todos", headers={"x-csrf-token": r.json()["csrf"]}).status_code == 200


def test_json_malformado_e_tipos_errados_dao_422_nao_500(cliente):
    for corpo in (b"{", b"[]", b'{"email": 5, "senha": null}', b'{"email": ["a"], "senha": {"x":1}}', b"\xff\xfe\x00"):
        r = cliente.post("/conta/login", content=corpo, headers={"content-type": "application/json"})
        assert r.status_code in (400, 422), (corpo, r.status_code)
    assert cliente.post("/conta/login", content=b"x=1", headers={"content-type": "text/plain"}).status_code in (415, 422)


def test_mass_assignment_nao_promove_a_admin():
    c = TestClient(app)
    r = c.post("/conta/cadastro", json={"email": "masa@exemplo.com", "senha": "uma frase bem longa 2026", "papel": "admin", "mfa_ativo": True, "email_verificado": True})
    assert r.status_code == 202
    with SessionLocal() as db:
        u = db.scalar(select(Usuario).where(Usuario.email_norm == "masa@exemplo.com"))
        assert u.papel == "usuario" and not u.mfa_ativo and not u.email_verificado        # campos extras são ignorados
