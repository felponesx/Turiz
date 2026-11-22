"""Contas: senhas Argon2id, login sem enumeração, bloqueio progressivo, sessões, CSRF, IDOR, MFA, recuperação, LGPD."""
import time
from datetime import datetime, timedelta, timezone
import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.conta import cripto, email as correio, senhas
from app.conta.cli import criar_usuario
from app.db import SessionLocal
from app.main import app
from app.seguranca import limites
from app.seguranca.modelos import Auditoria, FavoritoUsuario, Sessao, TokenConta, Usuario

SENHA = "uma frase bem longa 2026"


@pytest.fixture(autouse=True)
def correio_teste(monkeypatch):
    monkeypatch.setenv("TURIZ_EMAIL_BACKEND", "teste")
    correio.CAIXA_TESTE.clear()


def novo_cliente():
    return TestClient(app, base_url="http://testserver")


def cadastrar(c, email, senha=SENHA):
    return c.post("/conta/cadastro", json={"email": email, "senha": senha, "nome": "Teste"})


def entrar(c, email, senha=SENHA, **extra):
    return c.post("/conta/login", json={"email": email, "senha": senha, **extra})


def com_csrf(c, r):
    return {"x-csrf-token": r.json()["csrf"]}


def usuario_logado(email):
    c = novo_cliente()
    assert cadastrar(c, email).status_code == 202
    r = entrar(c, email)
    assert r.status_code == 200
    return c, com_csrf(c, r)


# ---------------------------------------------------------------- senhas
def test_senha_e_guardada_como_argon2id():
    c = novo_cliente()
    cadastrar(c, "hash@exemplo.com")
    with SessionLocal() as db:
        u = db.scalar(select(Usuario).where(Usuario.email_norm == "hash@exemplo.com"))
        assert u.senha_hash.startswith("$argon2id$") and SENHA not in u.senha_hash


@pytest.mark.parametrize("senha,trecho", [("curta", "pelo menos"), ("1234567890", "fácil"), ("a" * 12, "fácil"), ("ab" * 65, "máximo"), ("meuemail-teste99", "e-mail")])
def test_politica_de_senha(senha, trecho):
    c = novo_cliente()
    r = c.post("/conta/cadastro", json={"email": "meuemail@exemplo.com", "senha": senha})
    assert r.status_code == 422 and trecho in r.json()["detail"]


def test_verificar_com_conta_inexistente_leva_o_mesmo_tempo():
    h = senhas.hash_senha(SENHA)
    t = time.perf_counter(); senhas.verificar("errada-errada-1", h); com_conta = time.perf_counter() - t
    t = time.perf_counter(); senhas.verificar("errada-errada-1", None); sem_conta = time.perf_counter() - t
    assert 0.4 < sem_conta / com_conta < 2.5          # sem atalho: não dá para descobrir quais e-mails existem pelo tempo de resposta


# ---------------------------------------------------------------- cadastro/login sem enumeração
def test_cadastro_resposta_identica_para_email_novo_e_existente():
    c = novo_cliente()
    a = cadastrar(c, "dup@exemplo.com"); b = cadastrar(c, "DUP@exemplo.com")
    assert a.status_code == b.status_code == 202 and a.json() == b.json()
    with SessionLocal() as db:
        assert len(db.scalars(select(Usuario).where(Usuario.email_norm == "dup@exemplo.com")).all()) == 1


def test_login_mesma_resposta_para_senha_errada_e_conta_inexistente():
    c = novo_cliente(); cadastrar(c, "enum@exemplo.com")
    a = entrar(c, "enum@exemplo.com", "senha totalmente errada"); b = entrar(c, "naoexiste@exemplo.com", "senha totalmente errada")
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_login_define_cookies_seguros():
    c = novo_cliente(); cadastrar(c, "cookie@exemplo.com")
    r = entrar(c, "cookie@exemplo.com")
    sc = [h for h in r.headers.get_list("set-cookie")]
    sessao = next(x for x in sc if x.startswith("turiz_sessao="))
    assert "HttpOnly" in sessao and "SameSite=lax" in sessao.replace("Lax", "lax") and "Path=/" in sessao
    csrf = next(x for x in sc if x.startswith("turiz_csrf="))
    assert "HttpOnly" not in csrf                                  # o front precisa ler este para enviar no cabeçalho


def test_cookie_secure_em_https(monkeypatch):
    monkeypatch.setenv("TURIZ_FORCE_HTTPS", "1")
    c = novo_cliente(); cadastrar(c, "secure@exemplo.com")
    r = entrar(c, "secure@exemplo.com")
    assert "Secure" in next(x for x in r.headers.get_list("set-cookie") if x.startswith("turiz_sessao="))


def test_bloqueio_progressivo_por_conta():
    c = novo_cliente(); cadastrar(c, "forca@exemplo.com")
    for _ in range(5):
        assert entrar(c, "forca@exemplo.com", "tentativa errada 123").status_code in (401, 429)
        limites.AUTH_FALHA.reiniciar()                       # isola o bloqueio por conta do bloqueio por IP
    assert entrar(c, "forca@exemplo.com").status_code == 401   # senha CERTA, mas a conta está em pausa temporária
    with SessionLocal() as db:
        u = db.scalar(select(Usuario).where(Usuario.email_norm == "forca@exemplo.com"))
        assert u.bloqueado_ate is not None
        u.bloqueado_ate = datetime.now(timezone.utc) - timedelta(seconds=1)      # o tempo passou: nada é permanente
        db.commit()
    assert entrar(c, "forca@exemplo.com").status_code == 200


def test_credential_stuffing_por_ip_bloqueia_temporariamente():
    c = novo_cliente()
    cods = [entrar(c, f"vitima{i}@exemplo.com", "senha vazada qualquer 1").status_code for i in range(14)]
    assert 429 in cods
    assert entrar(c, "vitima0@exemplo.com").headers.get("retry-after")


# ---------------------------------------------------------------- sessões e CSRF
def test_sessao_exige_csrf_no_cookie_mas_nao_no_bearer():
    c, csrf = usuario_logado("csrf@exemplo.com")
    assert c.get("/conta/eu").status_code == 200
    assert c.patch("/conta/eu", json={"nome": "X"}).status_code == 403                    # sem token CSRF
    assert c.patch("/conta/eu", json={"nome": "X"}, headers={"x-csrf-token": "errado"}).status_code == 403
    assert c.patch("/conta/eu", json={"nome": "X"}, headers={**csrf, "origin": "https://site-malicioso.example"}).status_code == 403
    assert c.patch("/conta/eu", json={"nome": "Novo"}, headers=csrf).json()["nome"] == "Novo"
    api = novo_cliente(); api.post("/conta/cadastro", json={"email": "bearer@exemplo.com", "senha": SENHA})
    tok = entrar(api, "bearer@exemplo.com", retornar_token=True).json()["token"]
    api.cookies.clear()
    assert api.patch("/conta/eu", json={"nome": "App"}, headers={"authorization": f"Bearer {tok}"}).status_code == 200


def test_token_de_sessao_nao_fica_no_banco_em_texto_puro():
    c = novo_cliente(); cadastrar(c, "hashsess@exemplo.com")
    tok = entrar(c, "hashsess@exemplo.com", retornar_token=True).json()["token"]
    with SessionLocal() as db:
        hashes = [s.token_hash for s in db.scalars(select(Sessao))]
    assert tok not in hashes and all(len(h) == 64 for h in hashes)


def test_sessao_expirada_ociosa_e_revogada_sao_recusadas():
    c, csrf = usuario_logado("expira@exemplo.com")
    with SessionLocal() as db:
        s = db.scalars(select(Sessao).order_by(Sessao.id.desc())).first()
        s.ultimo_uso_em = datetime.now(timezone.utc) - timedelta(days=8); db.commit()
    assert c.get("/conta/eu").status_code == 401                                             # ociosa há mais de 7 dias
    c, csrf = usuario_logado("expira2@exemplo.com")
    with SessionLocal() as db:
        s = db.scalars(select(Sessao).order_by(Sessao.id.desc())).first()
        s.expira_em = datetime.now(timezone.utc) - timedelta(seconds=1); db.commit()
    assert c.get("/conta/eu").status_code == 401                                             # passou do limite absoluto
    c, csrf = usuario_logado("logout@exemplo.com")
    assert c.post("/conta/logout", headers=csrf).status_code == 200
    assert c.get("/conta/eu").status_code == 401


def test_sessoes_so_do_proprio_usuario_sem_idor():
    a, csrf_a = usuario_logado("a@exemplo.com"); b, csrf_b = usuario_logado("b@exemplo.com")
    id_b = next(s["id"] for s in b.get("/conta/sessoes").json())
    assert a.delete(f"/conta/sessoes/{id_b}", headers=csrf_a).status_code == 404            # a sessão do outro "não existe"
    assert b.get("/conta/eu").status_code == 200
    assert all(s["id"] != id_b for s in a.get("/conta/sessoes").json())
    assert a.delete("/conta/sessoes/99999999", headers=csrf_a).status_code == 404


def test_favoritos_isolados_por_usuario():
    a, csrf_a = usuario_logado("fa@exemplo.com"); b, csrf_b = usuario_logado("fb@exemplo.com")
    assert a.put("/conta/favoritos/lugar/api-123", headers=csrf_a).status_code == 200
    assert a.put("/conta/favoritos/lugar/api-123", headers=csrf_a).status_code == 200      # idempotente
    assert b.get("/conta/favoritos").json() == []                                           # B não vê o favorito de A
    assert [f["ref"] for f in a.get("/conta/favoritos").json()] == ["api-123"]
    b.delete("/conta/favoritos/lugar/api-123", headers=csrf_b)                              # apagar "o mesmo" não mexe no de A
    assert len(a.get("/conta/favoritos").json()) == 1
    assert a.put("/conta/favoritos/tipo-invalido/x", headers=csrf_a).status_code == 422
    assert a.put("/conta/favoritos/lugar/<script>", headers=csrf_a).status_code == 422
    assert novo_cliente().get("/conta/favoritos").status_code == 401                        # sem sessão não vê nada


def test_nenhuma_rota_de_conta_aceita_id_de_usuario():
    for rota in app.routes:
        caminho = getattr(rota, "path", "")
        if caminho.startswith("/conta"):
            assert "{usuario" not in caminho and "{user" not in caminho, caminho            # dono sempre vem da sessão


# ---------------------------------------------------------------- senha, recuperação, e-mail
def test_trocar_senha_derruba_outras_sessoes():
    a, csrf = usuario_logado("troca@exemplo.com")
    outro = novo_cliente(); entrar(outro, "troca@exemplo.com")
    assert a.post("/conta/senha", json={"senha_atual": "errada errada 12", "senha_nova": "outra frase segura 99"}, headers=csrf).status_code == 401
    assert a.post("/conta/senha", json={"senha_atual": SENHA, "senha_nova": "outra frase segura 99"}, headers=csrf).status_code == 200
    assert outro.get("/conta/eu").status_code == 401 and a.get("/conta/eu").status_code == 200
    assert entrar(novo_cliente(), "troca@exemplo.com", SENHA).status_code == 401
    assert entrar(novo_cliente(), "troca@exemplo.com", "outra frase segura 99").status_code == 200


def test_recuperacao_de_senha_token_unico_expira_e_derruba_sessoes():
    a, _ = usuario_logado("rec@exemplo.com"); c = novo_cliente()
    g1 = c.post("/conta/recuperar", json={"email": "rec@exemplo.com"}); g2 = c.post("/conta/recuperar", json={"email": "ninguem@exemplo.com"})
    assert g1.status_code == g2.status_code == 202 and g1.json() == g2.json()               # não revela se o e-mail existe
    envios = [x for x in correio.CAIXA_TESTE if x[0] == "recuperar_senha"]
    assert len(envios) == 1 and envios[0][1] == "rec@exemplo.com"
    token = envios[0][2]
    with SessionLocal() as db:
        assert token not in [t.token_hash for t in db.scalars(select(TokenConta))]          # só o hash fica guardado
    c.post("/conta/recuperar", json={"email": "rec@exemplo.com"})                          # novo pedido invalida o anterior
    assert c.post("/conta/recuperar/confirmar", json={"token": token, "senha_nova": "senha nova bem longa 1"}).status_code == 400
    token2 = [x for x in correio.CAIXA_TESTE if x[0] == "recuperar_senha"][-1][2]
    assert c.post("/conta/recuperar/confirmar", json={"token": token2, "senha_nova": "fraca"}).status_code == 422
    assert c.post("/conta/recuperar/confirmar", json={"token": token2, "senha_nova": "senha nova bem longa 1"}).status_code == 200
    assert c.post("/conta/recuperar/confirmar", json={"token": token2, "senha_nova": "senha nova bem longa 2"}).status_code == 400   # uso único
    assert a.get("/conta/eu").status_code == 401                                             # conta pode estar comprometida: todos saem
    assert entrar(novo_cliente(), "rec@exemplo.com", "senha nova bem longa 1").status_code == 200
    token3 = None
    c.post("/conta/recuperar", json={"email": "rec@exemplo.com"}); token3 = [x for x in correio.CAIXA_TESTE if x[0] == "recuperar_senha"][-1][2]
    with SessionLocal() as db:
        for t in db.scalars(select(TokenConta).where(TokenConta.tipo == "recuperar_senha", TokenConta.usado_em.is_(None))):
            t.expira_em = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert c.post("/conta/recuperar/confirmar", json={"token": token3, "senha_nova": "senha nova bem longa 3"}).status_code == 400   # expirado


def test_trocar_email_exige_senha_e_nao_revela_existentes():
    a, csrf = usuario_logado("troca-email@exemplo.com"); usuario_logado("ocupado@exemplo.com")
    assert a.post("/conta/email", json={"senha": "errada errada 1", "novo_email": "novo@exemplo.com"}, headers=csrf).status_code == 401
    ok = a.post("/conta/email", json={"senha": SENHA, "novo_email": "novo-email@exemplo.com"}, headers=csrf)
    ocupado = a.post("/conta/email", json={"senha": SENHA, "novo_email": "ocupado@exemplo.com"}, headers=csrf)
    assert ok.status_code == ocupado.status_code == 202 and ok.json() == ocupado.json()
    token = [x for x in correio.CAIXA_TESTE if x[0] == "trocar_email"]
    assert len(token) == 1 and token[0][1] == "novo-email@exemplo.com"
    assert a.get("/conta/eu").json()["email"] == "troca-email@exemplo.com"                 # só muda depois de confirmar
    assert novo_cliente().post("/conta/email/confirmar", json={"token": token[0][2]}).status_code == 200
    assert a.get("/conta/eu").json()["email"] == "novo-email@exemplo.com"


# ---------------------------------------------------------------- MFA e administração
def _admin(email="adm@exemplo.com"):
    with SessionLocal() as db:
        criar_usuario(db, email, SENHA, "admin")
    c = novo_cliente(); r = entrar(c, email)
    return c, com_csrf(c, r), r.json()


def test_admin_sem_mfa_nao_acessa_nada_administrativo_e_com_mfa_sim():
    c, csrf, corpo = _admin()
    assert corpo["mfa_configuracao_necessaria"] is True
    assert c.get("/conta/admin/resumo").status_code == 403                                   # senha sozinha não basta para admin
    ini = c.post("/conta/mfa/iniciar", headers=csrf)
    assert ini.status_code == 200
    segredo = ini.json()["segredo"]
    with SessionLocal() as db:
        guardado = db.scalar(select(Usuario).where(Usuario.email_norm == "adm@exemplo.com")).mfa_segredo
    assert guardado != segredo and cripto.decifrar(guardado) == segredo                        # segredo TOTP cifrado no banco
    assert c.post("/conta/mfa/confirmar", json={"codigo": "000000"}, headers=csrf).status_code == 401
    ok = c.post("/conta/mfa/confirmar", json={"codigo": pyotp.TOTP(segredo).now()}, headers=csrf)
    assert ok.status_code == 200 and len(ok.json()["codigos_de_recuperacao"]) == 8
    assert c.get("/conta/admin/resumo").status_code == 200                                     # agora sim
    assert c.post("/conta/mfa/desativar", json={"senha": SENHA, "codigo": "000000"}, headers=csrf).status_code == 403   # admin não desativa MFA
    # novo login: precisa do código, e o mesmo código não pode ser reutilizado (anti-replay)
    c2 = novo_cliente()
    r = entrar(c2, "adm@exemplo.com")
    assert r.status_code == 401 and r.headers.get("x-mfa") == "necessario"
    assert entrar(c2, "adm@exemplo.com", codigo="123456").status_code == 401
    limites.reiniciar_todos()
    with SessionLocal() as db:
        u = db.scalar(select(Usuario).where(Usuario.email_norm == "adm@exemplo.com")); u.mfa_ultimo_passo = 0; u.falhas_login = 0; u.bloqueado_ate = None; db.commit()
    codigo = pyotp.TOTP(segredo).now()
    assert entrar(c2, "adm@exemplo.com", codigo=codigo).status_code == 200
    assert c2.get("/conta/admin/resumo").status_code == 200
    assert entrar(novo_cliente(), "adm@exemplo.com", codigo=codigo).status_code == 401       # replay do mesmo código é recusado
    # código de recuperação: uso único
    rec = ok.json()["codigos_de_recuperacao"][0]
    limites.reiniciar_todos()
    assert entrar(novo_cliente(), "adm@exemplo.com", codigo=rec).status_code == 200
    limites.reiniciar_todos()
    assert entrar(novo_cliente(), "adm@exemplo.com", codigo=rec).status_code == 401


def test_usuario_comum_nao_acessa_rota_de_admin():
    c, csrf = usuario_logado("comum@exemplo.com")
    assert c.get("/conta/admin/resumo").status_code == 403
    assert novo_cliente().get("/conta/admin/resumo").status_code == 401


def test_operacoes_sensiveis_pedem_reautenticacao_recente():
    c, csrf = usuario_logado("reauth@exemplo.com")
    assert c.get("/conta/exportar").status_code == 200                                         # login acabou de acontecer
    with SessionLocal() as db:
        s = db.scalars(select(Sessao).order_by(Sessao.id.desc())).first()
        s.reauth_em = datetime.now(timezone.utc) - timedelta(minutes=30); db.commit()
    r = c.get("/conta/exportar")
    assert r.status_code == 403 and r.headers["x-reauth"] == "necessaria"
    assert c.post("/conta/reautenticar", json={"senha": "errada errada 1"}, headers=csrf).status_code == 401
    assert c.post("/conta/reautenticar", json={"senha": SENHA}, headers=csrf).status_code == 200
    assert c.get("/conta/exportar").status_code == 200


# ---------------------------------------------------------------- LGPD: exportar e excluir
def test_exportar_e_excluir_conta():
    c, csrf = usuario_logado("lgpd@exemplo.com")
    c.put("/conta/favoritos/evento/r1", headers=csrf)
    dados = c.get("/conta/exportar").json()
    assert dados["conta"]["email"] == "lgpd@exemplo.com" and dados["favoritos"] == [{"tipo": "evento", "ref": "r1"}]
    assert "senha_hash" not in str(dados) and "$argon2" not in str(dados)                       # nunca exporta o hash
    assert c.request("DELETE", "/conta", json={"senha": "errada errada 1"}, headers=csrf).status_code == 401
    assert c.request("DELETE", "/conta", json={"senha": SENHA}, headers=csrf).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(Usuario).where(Usuario.email_norm == "lgpd@exemplo.com")) is None
        assert db.scalars(select(FavoritoUsuario).where(FavoritoUsuario.ref == "r1")).first() is None
        assert db.scalars(select(Auditoria).where(Auditoria.detalhe.like("conta_excluida%"))).first() is not None
    assert entrar(novo_cliente(), "lgpd@exemplo.com").status_code == 401
    assert c.get("/conta/eu").status_code == 401


def test_novo_dispositivo_gera_alerta():
    a, _ = usuario_logado("alerta@exemplo.com")
    correio.CAIXA_TESTE.clear()
    import app.conta.api as api_conta
    original = api_conta.ip_hash
    api_conta.ip_hash = lambda ip: "outro-ip-" + ip                   # simula acesso de outro lugar
    try:
        assert entrar(novo_cliente(), "alerta@exemplo.com").status_code == 200
    finally:
        api_conta.ip_hash = original
    assert any(x[0] == "alerta_login" for x in correio.CAIXA_TESTE)
    assert any(a["resultado"] == "alerta" for a in a.get("/conta/atividade").json())


def test_respostas_de_conta_nao_vao_para_cache():
    c, _ = usuario_logado("cache@exemplo.com")
    assert c.get("/conta/eu").headers["cache-control"] == "no-store"


def test_cripto_exige_chave_em_producao(monkeypatch):
    monkeypatch.setenv("TURIZ_ENV", "production"); monkeypatch.delenv("TURIZ_ENC_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TURIZ_ENC_KEY"):
        cripto.cifrar("x")
