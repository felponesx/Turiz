"""Conector com navegador (Playwright) para páginas de eventos que só aparecem depois de executar JavaScript.

Regras: respeita robots.txt; um navegador, uma página por vez, pausa entre páginas; NÃO tenta contornar CAPTCHA, login, paywall ou
bloqueios (ao detectá-los, a fonte vira "bloqueada" e a coleta segue para as demais). Lê o JSON-LD (schema.org) da página já renderizada.
Playwright é opcional (requirements-navegador.txt); sem ele a fonte fica "aguardando_dependencia", sem afetar as outras.
"""
import os
import re
import time
from typing import Iterator
from .base import Conector, Contexto, ErroFonte, FonteBloqueada, registrar
from .feeds import bruto_de_evento_site

SINAIS_BLOQUEIO = re.compile(r"captcha|are you a robot|verify you are human|acesso negado|access denied|cloudflare|attention required|unusual traffic|"
                             r"tráfego incomum|verificação de segurança|sou humano", re.I)


def detectar_bloqueio(html: str, status: int | None = None) -> str:
    if status in (401, 403, 429):
        return f"HTTP {status}"
    m = SINAIS_BLOQUEIO.search(html[:20000] if html else "")
    return f"página de verificação detectada ({m.group(0)})" if m else ""


@registrar
class Navegador(Conector):
    tipo = "navegador"
    descricao = "Páginas dependentes de JavaScript (Playwright), com robots.txt, pausa e sem contornar bloqueios"

    def coletar(self, ctx: Contexto) -> Iterator:
        try:
            from playwright.sync_api import sync_playwright, Error as PwError
        except ImportError:
            raise ErroFonte("Playwright não instalado (pip install playwright && playwright install chromium)")
        from ...sources import sites
        c = ctx.config
        cli = ctx.requisitor.client
        urls = c.get("urls") or [c["url"]]
        cidade, pausa = c.get("cidade", ""), float(c.get("pausa", 3))
        permitidas = []
        for u in urls:
            if sites.permitido(u, cli):
                permitidas.append(u)
            else:
                ctx.stats.avisos.append("URL ignorada pelo robots.txt")
        if not permitidas:
            raise FonteBloqueada("robots.txt não permite a coleta")
        n = 0
        with sync_playwright() as pw:
            kw = {"headless": True, "args": ["--no-sandbox"]}
            exe = os.getenv("TURIZ_CHROMIUM") or c.get("chromium")
            if exe:
                kw["executable_path"] = exe
            try:
                nav = pw.chromium.launch(**kw)
            except PwError as exc:
                raise ErroFonte(f"não foi possível iniciar o navegador: {str(exc)[:120]}")
            try:
                pag = nav.new_context(user_agent="TurizEventosBot/1.0 (+https://github.com/felponesx/Turiz)").new_page()
                for u in permitidas:
                    try:
                        resp = pag.goto(u, wait_until="networkidle", timeout=int(c.get("timeout_ms", 30000)))
                        if c.get("aguardar"):
                            pag.wait_for_selector(c["aguardar"], timeout=int(c.get("timeout_ms", 30000)))
                        html = pag.content()
                    except PwError as exc:
                        ctx.stats.erros += 1
                        ctx.stats.avisos.append(f"falha ao abrir página: {str(exc)[:80]}")
                        continue
                    ctx.stats.paginas += 1
                    motivo = detectar_bloqueio(html, resp.status if resp else None)
                    if motivo:
                        raise FonteBloqueada(f"{motivo}: não contornamos bloqueios")
                    _, evs = sites.extrair(html, u, "evento")
                    for e in evs:
                        if sites.da_cidade(e, cidade):
                            e["_cidade"] = cidade
                            yield bruto_de_evento_site(e, ctx.slug)
                            n += 1
                            if ctx.limite and n >= ctx.limite:
                                return
                    time.sleep(pausa)
            finally:
                nav.close()
