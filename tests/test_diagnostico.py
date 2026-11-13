import httpx
from app.sources import diagnostico


def cliente(respostas):
    def h(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text=respostas.get("robots", ""))
        corpo, status = respostas.get(req.url.host, ("", 200))
        return httpx.Response(status, text=corpo)
    return httpx.Client(transport=httpx.MockTransport(h), follow_redirects=True)


def f(host, tipo="html"):
    return {"id": host, "categoria": "evento", "tipo": tipo, "url": f"https://{host}/x"}


def test_classifica_resultados():
    ev = '<script type="application/ld+json">{"@type":"MusicEvent","name":"A"}</script>'
    c = cliente({"ok.com": (ev, 200), "vazio.com": ("<html></html>", 200), "bloq.com": ("Just a moment... cloudflare", 403),
                 "api.com": ("", 401), "quebrado.com": ("", 500)})
    r = {x: diagnostico.testar(f(x, "api" if x == "api.com" else "html"), c)["resultado"] for x in ("ok.com", "vazio.com", "bloq.com", "api.com", "quebrado.com")}
    assert r == {"ok.com": "ok_jsonld", "vazio.com": "abre_sem_dados_estruturados", "bloq.com": "bloqueado", "api.com": "precisa_de_chave", "quebrado.com": "erro_500"}


def test_respeita_robots_e_relatorio():
    c = cliente({"robots": "User-agent: *\nDisallow: /", "x.com": ("<html></html>", 200)})
    r = diagnostico.testar(f("x.com"), c)
    assert r["resultado"] == "robots_proibe" and r["robots_permite"] is False
    md = diagnostico.relatorio_md([r], "2026-11-13 12:00")
    assert "robots.txt proíbe" in md and "| [x.com](https://x.com/x) |" in md


def test_inacessivel():
    def boom(req):
        raise httpx.ConnectError("sem rota")
    c = httpx.Client(transport=httpx.MockTransport(boom))
    assert diagnostico.testar(f("y.com"), c)["resultado"] == "inacessivel"
