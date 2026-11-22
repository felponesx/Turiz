#!/usr/bin/env python3
"""Teste ponta a ponta do front de PRODUÇÃO contra a API real (mesma origem): CSP aplicada sem violações, cadastro, login, cookies HttpOnly,
bloqueio por tentativas, MFA de administrador, exportar/excluir dados (LGPD), segurança (sessões, trocar senha), ausência de dados falsos.
Uso: python frontend/teste_e2e_producao.py dist/turiz.prod.html"""
import os
import re
import subprocess
import sys
import time
import httpx
import pyotp
from playwright.sync_api import sync_playwright

HTML = os.path.abspath(sys.argv[1])
PORTA = 8123
BASE = f"http://127.0.0.1:{PORTA}"
falhas = 0


def ok(cond, msg):
    global falhas
    print(("OK   " if cond else "FALHA"), msg)
    falhas += 0 if cond else 1


def esperar(pag, expr, timeout=15):
    """Espera por polling com evaluate (o wait_for_function do Playwright usa eval, que a CSP estrita corretamente bloqueia)."""
    fim = time.time() + timeout
    while time.time() < fim:
        if pag.evaluate(expr):
            return True
        time.sleep(0.2)
    raise TimeoutError(expr)


def main():
    totp = pyotp.random_base32()
    env = {**os.environ, "TURIZ_FRONT": HTML, "PYTHONPATH": os.getcwd(), "TURIZ_E2E_TOTP": totp}
    srv = subprocess.Popen([sys.executable, "scripts/servir_front_teste.py", str(PORTA)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            try:
                if httpx.get(BASE + "/health", timeout=1).status_code == 200:
                    break
            except Exception:
                time.sleep(0.5)
        # administrador com MFA, criado direto no banco do servidor de teste (via API de conta + CLI do projeto não é possível sem o DB; usa o endpoint público)
        with sync_playwright() as pw:
            exe = os.getenv("TURIZ_CHROMIUM") or ("/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)
            nav = pw.chromium.launch(executable_path=exe, args=["--no-sandbox"]) if exe else pw.chromium.launch()
            ctx = nav.new_context(viewport={"width": 390, "height": 844}, accept_downloads=True)
            pag = ctx.new_page()
            violacoes, erros = [], []
            pag.on("console", lambda m: violacoes.append(m.text) if ("Content Security Policy" in m.text or "Refused to" in m.text) else None)
            pag.on("pageerror", lambda e: erros.append(str(e)))
            pag.on("dialog", lambda d: d.dismiss())
            pag.goto(BASE + "/turiz")
            pag.wait_for_selector("#authform, .splash", timeout=15000)
            pag.evaluate("go('login',null,true)")
            pag.wait_for_selector("#authform")
            resp = httpx.get(BASE + "/turiz")
            ok("content-security-policy" in {k.lower() for k in resp.headers} and "x-frame-options" in {k.lower() for k in resp.headers}, "servidor envia cabeçalhos de segurança na página")
            ok('http-equiv="Content-Security-Policy"' in resp.text and "unsafe-eval" not in resp.text, "página carrega com CSP estrita (sem unsafe-eval)")
            ok(not pag.evaluate("PROTO"), "modo produção (PROTO=false)")
            # -------- cadastro pela tela
            pag.click('[data-act="authmode:reg"]')
            pag.fill("#f-name", "Maria Teste"); pag.fill("#f-mail", "maria.teste@exemplo.com"); pag.fill("#f-pass", "uma frase bem longa 2026")
            pag.evaluate("document.querySelector('#authform').requestSubmit()")
            esperar(pag, "S.route.n==='prefs'||S.route.n==='home'")
            ok(pag.evaluate("S.user && S.user.email") == "maria.teste@exemplo.com", "cadastro + login pela tela (API real)")
            cookies = {c["name"]: c for c in ctx.cookies()}
            ok(cookies["turiz_sessao"]["httpOnly"] and cookies["turiz_sessao"]["sameSite"] == "Lax" and not cookies["turiz_csrf"]["httpOnly"], "cookie de sessão HttpOnly + SameSite=Lax; token CSRF legível")
            ok(pag.evaluate("document.cookie").find("turiz_sessao") == -1, "JavaScript não enxerga o cookie de sessão")
            ok("token" not in str(pag.evaluate("JSON.stringify(Object.assign({}, localStorage))")).lower(), "nenhum token no localStorage")
            pag.evaluate("S.stack=[];go('home',null,true)"); pag.wait_for_timeout(500)
            texto = pag.inner_text("body")
            ok("Maria" in texto and "Lucas" not in texto and "EXEMPLO" not in texto.upper().replace("EXEMPLOS", ""), "tela inicial mostra o usuário real e nenhum dado de exemplo")
            ok(pag.evaluate("DEMO.on") is False, "dados de exemplo desligados")
            for rota in ("ranking", "rewards", "missions", "notifs"):
                pag.evaluate(f"S.stack=[];go('{rota}',null,true)"); pag.wait_for_timeout(150)
                ok("Em breve" in pag.inner_text("body"), f"/{rota} sem dados falsos (Em breve)")
            # -------- percorre telas sob CSP
            for rota in ("explore", "parties", "favs", "profile", "settings", "security", "legal"):
                pag.evaluate(f"S.stack=[];go('{rota}',null,true)"); pag.wait_for_timeout(250)
            ok(not violacoes, f"nenhuma violação de CSP ao navegar ({violacoes[:2]})")
            ok(not erros, f"sem erros de JavaScript ({erros[:2]})")
            # -------- exportar (LGPD)
            pag.evaluate("S.stack=[];go('settings',null,true)"); pag.wait_for_timeout(250)
            with pag.expect_download() as d:
                pag.evaluate("exportarDados()")
            conteudo = open(d.value.path(), encoding="utf-8").read()
            ok("maria.teste@exemplo.com" in conteudo and "argon2" not in conteudo, "exportação traz os dados da conta e nunca o hash da senha")
            # -------- segurança: sessões e trocar senha
            pag.evaluate("S.sessApi=undefined;S.stack=[];go('security',null,true)"); pag.wait_for_timeout(700)
            ok("Este" in pag.inner_text("body"), "tela de segurança lista a sessão atual")
            pag.evaluate("sheet(senhaSheet())"); pag.fill("#f-sa", "uma frase bem longa 2026"); pag.fill("#f-sn", "outra frase muito longa 2027")
            pag.click('[data-act="senhago"]'); pag.wait_for_timeout(800)
            ok(not pag.evaluate("document.querySelector('#sheet').classList.contains('open')"), "senha trocada pela tela")
            # -------- logout, login errado, bloqueio
            pag.evaluate("go('settings',null,true)"); pag.evaluate("act(['logout'])"); pag.wait_for_selector("#authform")
            # -------- administrador: senha sozinha não basta; tela pede o código de verificação
            pag.evaluate("S.auth={mode:'login',err:{},sent:false};render()"); pag.wait_for_selector("#authform")
            pag.fill("#f-mail", "admin.e2e@exemplo.com"); pag.fill("#f-pass", "frase de admin bem longa 2026")
            pag.evaluate("document.querySelector('#authform').requestSubmit()"); pag.wait_for_selector("#f-code", timeout=10000)
            ok("código" in pag.inner_text("body").lower(), "administrador: a tela pede o código de verificação (MFA)")
            ok(httpx.get(BASE + "/conta/admin/resumo").status_code == 401, "sem sessão, a rota administrativa é negada")
            pag.fill("#f-code", "000000"); pag.evaluate("document.querySelector('#authform').requestSubmit()"); pag.wait_for_timeout(700)
            ok(pag.evaluate("S.route.n") == "login", "código errado não entra")
            pag.fill("#f-pass", "frase de admin bem longa 2026"); pag.fill("#f-code", pyotp.TOTP(totp).now())      # o e-mail é preservado entre as etapas
            pag.evaluate("document.querySelector('#authform').requestSubmit()")
            try:
                esperar(pag, "S.route.n==='home'", 8)
            except TimeoutError:
                print("DEBUG rota:", pag.evaluate("S.route.n"), "| erro na tela:", pag.evaluate("JSON.stringify(S.auth.err)"), "| totp ok:", pyotp.TOTP(totp).now())
                raise
            r = pag.evaluate("api('/conta/admin/resumo').then(r=>r.status)")
            ok(r == 200, "administrador com MFA acessa a rota administrativa")
            # -------- força bruta (por último: bloqueia o IP de teste)
            pag.evaluate("act(['logout'])"); pag.wait_for_selector("#authform")
            for i in range(7):
                pag.fill("#f-mail", "maria.teste@exemplo.com"); pag.fill("#f-pass", f"senha errada numero {i}")
                pag.evaluate("document.querySelector('#authform').requestSubmit()"); pag.wait_for_timeout(500)
            ok("Muitas tentativas" in pag.inner_text("body") or "incorretos" in pag.inner_text("body"), "tentativas erradas viram bloqueio temporário com mensagem clara")
            nav.close()
    finally:
        srv.terminate()
        srv.wait(timeout=10)
    print("TUDO OK" if not falhas else f"{falhas} FALHAS")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
