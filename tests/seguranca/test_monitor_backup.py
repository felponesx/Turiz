import json
import subprocess
import sys
import httpx
import importlib.util

spec = importlib.util.spec_from_file_location("monitorar", "scripts/monitorar.py")
monitorar = importlib.util.module_from_spec(spec); spec.loader.exec_module(monitorar)

SEGURO = {"x-content-type-options": "nosniff", "content-security-policy": "default-src 'none'", "referrer-policy": "no-referrer"}


def cliente(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_monitor_saudavel_nao_acusa_nada():
    def h(r):
        return httpx.Response(200, json={"ok": True}, headers=SEGURO) if r.url.path == "/health" else httpx.Response(404)
    assert monitorar.verificar("https://api.exemplo.com", cliente(h), checar_certificado=False) == []


def test_monitor_detecta_problemas():
    def fora(r): raise httpx.ConnectError("sem rede")
    monitorar.time.sleep = lambda s: None
    assert any("fora do ar" in p for p in monitorar.verificar("https://api.exemplo.com", cliente(fora), checar_certificado=False))
    def ruim(r):
        if r.url.path == "/docs":
            return httpx.Response(200, text="docs")
        return httpx.Response(500)
    p = monitorar.verificar("http://api.exemplo.com", cliente(ruim), checar_certificado=False)
    assert any("HTTPS" in x for x in p) and any("HTTP 500" in x for x in p) and any("cabeçalhos" in x for x in p) and any("/docs" in x for x in p)
    def sem_ok(r):
        return httpx.Response(200, json={"ok": False}, headers=SEGURO) if r.url.path == "/health" else httpx.Response(404)
    assert any("ok=true" in x for x in monitorar.verificar("https://a.com", cliente(sem_ok), checar_certificado=False))


def test_restauracao_real_dos_snapshots_passa():
    r = subprocess.run([sys.executable, "scripts/testar_restauracao.py"], capture_output=True, text=True)
    saida = json.loads(r.stdout[r.stdout.index("{"):])
    assert r.returncode == 0 and saida["ok"] and saida["integridade_sqlite"] == "ok" and saida["lugares_restaurados"] >= saida["lugares_esperados"] * 0.99


def test_snapshot_nunca_inclui_contas_de_usuario():
    """Backups em git não podem conter dados pessoais de usuários: só dados públicos coletados."""
    import gzip
    d = json.load(gzip.open("data/eventos_v2.json.gz", "rt", encoding="utf-8"))
    assert not ({"usuarios", "sessoes", "tokens_conta", "favoritos_usuario", "auditoria"} & set(d))
    import glob
    for arq in glob.glob("data/*.json"):
        assert not any(k in open(arq, encoding="utf-8").read(2000) for k in ("senha_hash", "token_hash", "mfa_segredo"))
