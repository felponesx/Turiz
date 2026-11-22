"""Proteções da API: cabeçalhos, limites, força bruta, escopos de chave, auditoria, entradas maliciosas, erros e timeout."""
import asyncio
import pytest
from sqlalchemy import select
from app.db import SessionLocal
from app.main import app
from app.models import Lugar
from app.seguranca import chaves, limites
from app.seguranca.modelos import Auditoria

H = {"x-api-key": "k"}


def test_docs_e_openapi_desligados_por_padrao(cliente):
    assert cliente.get("/docs").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404
    assert cliente.get("/redoc").status_code == 404


def test_cabecalhos_de_seguranca(cliente):
    h = cliente.get("/lugares?limit=1").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert "default-src 'none'" in h["content-security-policy"] and "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["referrer-policy"] and h["permissions-policy"] and h["x-request-id"]
    pagina = cliente.get("/")
    assert pagina.status_code == 200 and "script-src" in pagina.headers["content-security-policy"]
    assert cliente.get("/admin/saude", headers=H).headers["cache-control"] == "no-store"


def test_hsts_so_com_https_obrigatorio(cliente, monkeypatch):
    assert "strict-transport-security" not in cliente.get("/health").headers
    monkeypatch.setenv("TURIZ_FORCE_HTTPS", "1")
    assert "max-age=31536000" in cliente.get("/health").headers["strict-transport-security"]


def test_x_forwarded_for_falso_nao_burla_o_limite(cliente):
    limites.LEITURA.maximo = 5
    codigos = [cliente.get("/lugares/1/redes", headers={"x-forwarded-for": f"9.9.9.{i}"}).status_code for i in range(12)]
    assert 429 in codigos                                     # sem proxies configurados, o cabeçalho do cliente é ignorado
    r = cliente.get("/lugares/1/redes", headers={"x-forwarded-for": "1.2.3.4"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


def test_com_proxy_confiavel_usa_o_ip_escrito_pelo_proxy(cliente, monkeypatch):
    monkeypatch.setenv("TURIZ_PROXY_HOPS", "1")
    limites.LEITURA.maximo = 3
    # o cliente tenta forjar o primeiro valor; o proxy acrescenta o IP real por último
    cods = [cliente.get("/lugares/1/redes", headers={"x-forwarded-for": f"{i}.{i}.{i}.{i}, 8.8.8.8"}).status_code for i in range(8)]
    assert 429 in cods
    outro = cliente.get("/lugares/1/redes", headers={"x-forwarded-for": "6.6.6.6, 7.7.7.7"})
    assert outro.status_code != 429                           # outro IP real não é afetado


def test_bloqueio_progressivo_e_temporario_nao_permanente():
    l = limites.Limitador(2, 60, bloqueio_base_s=10, bloqueio_max_s=40)
    assert l.verificar("ip", 0)[0] and l.verificar("ip", 1)[0]
    ok, espera = l.verificar("ip", 2)
    assert not ok and espera == 10                            # 1ª reincidência: 10 s
    assert not l.verificar("ip", 5)[0]                        # ainda bloqueado
    assert l.verificar("ip", 13)[0] and l.verificar("ip", 14)[0]   # passou o tempo: volta a funcionar (nada permanente)
    ok, espera = l.verificar("ip", 15)
    assert not ok and espera == 20                            # 2ª reincidência: dobra
    assert l.verificar("outro", 15)[0]                        # outro cliente nunca é afetado


def test_forca_bruta_da_chave_bloqueia_temporariamente(cliente):
    cods = [cliente.post("/avaliacoes", json={}, headers={"x-api-key": f"errada{i}"}).status_code for i in range(12)]
    assert cods[0] == 401 and 429 in cods
    r = cliente.post("/avaliacoes", json={}, headers=H)       # durante o bloqueio nem a chave certa passa, mas é temporário
    assert r.status_code == 429 and "retry-after" in r.headers
    limites.reiniciar_todos()
    assert cliente.get("/admin/saude", headers=H).status_code == 200


def test_escopos_de_chave(cliente, monkeypatch):
    monkeypatch.setenv("TURIZ_API_KEYS", "coletor:ingest:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,moderador:moderacao:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb,dono:admin:cccccccccccccccccccccccccccccccc")
    ing, mod, adm = ({"x-api-key": c * 32} for c in "abc")
    assert cliente.get("/admin/saude", headers=ing).status_code == 401              # ingest não vê saúde detalhada
    assert cliente.get("/admin/saude", headers=mod).status_code == 200
    assert cliente.get("/admin/eventos/fontes", headers=mod).status_code == 401     # moderação não administra fontes
    assert cliente.get("/admin/eventos/fontes", headers=adm).status_code == 200
    assert cliente.post("/ingest/lugares", json=[], headers=ing).status_code == 200
    assert cliente.patch("/avaliacoes/1", params={"status": "publicada"}, headers=ing).status_code == 401
    assert cliente.get("/admin/saude", headers=H).status_code == 200                # API_KEY legado continua valendo como admin


def test_chave_fraca_recusada_em_producao(monkeypatch):
    monkeypatch.setenv("TURIZ_ENV", "production")
    monkeypatch.setenv("API_KEY", "curta")
    with pytest.raises(RuntimeError, match="fraca"):
        chaves.carregar()
    monkeypatch.setenv("TURIZ_API_KEYS", "x:superadmin:abc")
    monkeypatch.setenv("API_KEY", "")
    with pytest.raises(RuntimeError, match="inválida"):
        chaves.carregar()


def test_auditoria_registra_sem_segredos(cliente, monkeypatch):
    monkeypatch.setenv("TURIZ_API_KEYS", "dono:admin:" + "z" * 40)
    cliente.get("/admin/saude", headers={"x-api-key": "z" * 40})
    cliente.get("/admin/saude", headers={"x-api-key": "chave-errada-xyz"})
    with SessionLocal() as db:
        linhas = db.scalars(select(Auditoria).order_by(Auditoria.id.desc()).limit(2)).all()
    assert {l.resultado for l in linhas} == {"autorizado", "negado"}
    texto = " ".join(f"{l.ator} {l.rota} {l.detalhe} {l.ip_hash}" for l in linhas)
    assert "z" * 40 not in texto and "chave-errada-xyz" not in texto and "testclient" not in texto   # sem chaves e sem IP puro
    assert any(l.ator == "dono" for l in linhas)


def test_ingest_limites_e_sanitizacao(cliente, monkeypatch):
    monkeypatch.setenv("TURIZ_MAX_INGEST_ITENS", "3")
    assert cliente.post("/ingest/lugares", json=[{"fonte": "t", "fonte_id": str(i), "tipo": "bar", "nome": "x"} for i in range(4)], headers=H).status_code == 413
    assert cliente.post("/ingest/lugares", json=[{"nome": "sem fonte"}], headers=H).status_code == 422
    r = cliente.post("/ingest/lugares", json=[{"fonte": "sec", "fonte_id": "js1", "tipo": "bar", "nome": "Bar Esperto", "site": "javascript:alert(1)"}], headers=H)
    assert r.status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(Lugar).where(Lugar.fonte == "sec", Lugar.fonte_id == "js1")).site == ""   # esquema perigoso descartado


def test_corpo_grande_recusado(cliente, monkeypatch):
    monkeypatch.setenv("TURIZ_MAX_BODY", "2000")
    r = cliente.post("/avaliacoes", content=b"x" * 5000, headers={**H, "content-type": "application/json"})
    assert r.status_code == 413 and r.json()["detail"]


def test_curinga_like_vira_texto_literal(cliente):
    cliente.post("/ingest/lugares", json=[{"fonte": "lk", "fonte_id": "1", "tipo": "bar", "nome": "Bar 100% Carne"}, {"fonte": "lk", "fonte_id": "2", "tipo": "bar", "nome": "Bar Qualquer"}], headers=H)
    assert cliente.get("/lugares", params={"q": "%", "fonte": "lk"}).json()["total"] == 1       # só o que realmente tem "%"
    assert cliente.get("/lugares", params={"q": "_", "fonte": "lk"}).json()["total"] == 0
    assert cliente.get("/lugares", params={"q": "' OR 1=1 --", "fonte": "lk"}).json()["total"] == 0   # SQLi é só texto


def test_paginacao_com_limites(cliente):
    assert cliente.get("/lugares", params={"offset": 10**12}).status_code == 422
    assert cliente.get("/lugares", params={"limit": 100000}).status_code == 422
    assert cliente.get("/lugares", params={"limit": -1}).status_code == 422


def _rota_temporaria(caminho, fn):
    """Rota de teste colocada ANTES do mount estático (que responderia 404 a tudo)."""
    app.router.add_api_route(caminho, fn)
    app.router.routes.insert(0, app.router.routes.pop())


def test_erro_interno_nao_vaza_detalhes(cliente):
    async def boom():
        raise ValueError("SEGREDO-INTERNO caminho /home/user/x")
    _rota_temporaria("/__boom", boom)
    r = cliente.get("/__boom")
    assert r.status_code == 500 and "SEGREDO" not in r.text and "Traceback" not in r.text and r.json()["request_id"]
    app.router.routes.pop(0)


def test_timeout_de_requisicao(cliente, monkeypatch):
    monkeypatch.setenv("TURIZ_TIMEOUT_S", "1")
    async def lenta():
        await asyncio.sleep(3)
        return {"ok": 1}
    _rota_temporaria("/__lenta", lenta)
    r = cliente.get("/__lenta")
    app.router.routes.pop(0)
    assert r.status_code == 504


def test_mapa_inteiro_tem_cache(cliente):
    a = cliente.get("/lugares/geo")
    b = cliente.get("/lugares/geo")
    assert a.headers["cache-control"] == "public, max-age=300" and a.json() == b.json()


def test_rotas_caras_tem_limite_proprio(cliente):
    limites.CARA.maximo = 4
    cods = [cliente.get("/lugares/geo").status_code for _ in range(8)]
    assert cods.count(429) >= 3
    assert cliente.get("/lugares/1/redes").status_code != 429          # leitura comum continua livre


def test_health_publico_minimo(cliente):
    assert cliente.get("/health").json() == {"ok": True}
