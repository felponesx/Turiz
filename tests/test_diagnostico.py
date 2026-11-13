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


def test_listagem_sem_jsonld_mas_detalhes_com_evento():
    ev = '<script type="application/ld+json">{"@type":"Event","name":"A"}</script>'
    def h(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        if req.url.path == "/lista":
            return httpx.Response(200, text='<a href="/evento/a">A</a><a href="/evento/b">B</a><a href="/sobre">x</a>')
        return httpx.Response(200, text=ev)
    c = httpx.Client(transport=httpx.MockTransport(h), follow_redirects=True)
    r = diagnostico.testar({"id": "l", "categoria": "evento", "tipo": "html", "url": "https://l.com/lista"}, c)
    assert r["resultado"] == "ok_via_detalhes" and (r["detalhes_testados"], r["detalhes_com_evento"]) == (2, 2)
    assert "modo listagem" in diagnostico.relatorio_md([r], "x")


def test_testar_fonte_relatorio(tmp_path, monkeypatch):
    import testar_fonte
    ev = '<script type="application/ld+json">{"@type":"MusicEvent","name":"Show Z","startDate":"2026-12-01T20:00:00-03:00","offers":{"price":"50"}}</script>'
    def h(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        if req.url.path == "/lista":
            return httpx.Response(200, text='<a href="/evento/z">Z</a>')
        return httpx.Response(200, text=ev)
    real = httpx.Client
    monkeypatch.setattr(testar_fonte.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(h), follow_redirects=True))
    md = testar_fonte.testar_url("https://l.com/lista", True, r"^/evento/", 5, "evento")
    assert "1 eventos" in md and "Show Z" in md and "R$ 50.00" in md and "musica" in md
