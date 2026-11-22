#!/usr/bin/env python3
"""Gera o front de PRODUÇÃO a partir do protótipo: PROTO=false, sem login de teste, sem dados de exemplo, sem CDN/Google Fonts (fontes e jsQR
locais, vindos de frontend/vendor com hash), página completa com CSP estrita (scripts só por hash; sem handlers inline) e verificações
finais (sem segredos, sem CNPJ/e-mail nos dados embutidos, sem URLs de terceiros de código).

Uso: python build_producao.py turiz.html dist/turiz.html --vendor /caminho/frontend/vendor --empresa empresa.json --juridico-revisado
     (--permitir-pendente gera uma versão de HOMOLOGAÇÃO com campos vazios; nunca publique essa)"""
import argparse, base64, hashlib, json, re, sys

CAMPOS_EMPRESA = ("razao", "cnpj", "endereco", "contato", "encarregado", "prazoRemocao")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada"); ap.add_argument("saida")
    ap.add_argument("--vendor", required=True)
    ap.add_argument("--empresa", help="JSON com razao, cnpj, endereco, contato, encarregado, prazoRemocao (NÃO versionar)")
    ap.add_argument("--juridico-revisado", action="store_true", help="confirma que os textos legais foram revisados por advogado")
    ap.add_argument("--permitir-pendente", action="store_true")
    a = ap.parse_args()
    h = open(a.entrada, encoding="utf-8").read()
    erros = []

    empresa = json.load(open(a.empresa, encoding="utf-8")) if a.empresa else {}
    faltando = [c for c in CAMPOS_EMPRESA if not str(empresa.get(c, "")).strip()]
    if (faltando or not a.juridico_revisado) and not a.permitir_pendente:
        sys.exit("BUILD RECUSADO: " + (f"dados da empresa faltando: {faltando}. " if faltando else "") +
                 ("confirme a revisão jurídica dos textos com --juridico-revisado." if not a.juridico_revisado else ""))

    assert "const PROTO=true;" in h, "protótipo sem o modo de produção: rode patch_producao*.py"
    h = h.replace("const PROTO=true;", "const PROTO=false;")
    h = re.sub(r"const EMPRESA=\{[^}]*\};", lambda m: "const EMPRESA=" + json.dumps({c: str(empresa.get(c, "")) for c in CAMPOS_EMPRESA}, ensure_ascii=False).replace("</", "<\\/") + ";", h, count=1)
    # login de teste e simulações fora do arquivo (não só desligados)
    h, n = re.subn(r'\s*/\* DEV ONLY[^*]*\*/\s*if\(!reg&&mail==="admin"&&pass==="admin"\)\{remember\(true\);go\("home",null,true\);return\}', "", h)
    if n != 1:
        erros.append("não consegui remover o login de teste")
    h = re.sub(r'(<script type="application/json" id="api-fotos-ex">).*?(</script>)', r"\1{}\2", h, flags=re.S)       # sem fotos ilustrativas

    # dependências locais
    fonts_css = open(f"{a.vendor}/fonts.css", encoding="utf-8").read()
    def embutir(m):
        arq = f"{a.vendor}/{m.group(1)}"
        return "url(data:font/woff2;base64," + base64.b64encode(open(arq, "rb").read()).decode() + ")"
    fonts_css = re.sub(r"url\((fonts/[^)]+\.woff2)\)", embutir, fonts_css)
    h, n1 = re.subn(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/[^"]*">', lambda m: "<style>" + fonts_css + "</style>", h)
    h = re.sub(r'<link rel="preconnect" href="https://fonts\.[a-z.]+"[^>]*>\s*', "", h)
    jsqr = open(f"{a.vendor}/jsQR.js", encoding="utf-8").read()
    integ = json.load(open(f"{a.vendor}/INTEGRIDADE.json"))
    if "sha384-" + base64.b64encode(hashlib.sha384(jsqr.encode()).digest()).decode() != integ["jsQR.js"]["sri"]:
        erros.append("jsQR local não confere com o hash registrado")
    h, n2 = re.subn(r'<script src="https://cdn\.jsdelivr\.net/npm/jsqr@[^"]+"></script>', lambda m: "<script>" + jsqr.replace("</script", "<\\/script") + "</script>", h)
    if n1 != 1 or n2 != 1:
        erros.append(f"fontes/jsQR não substituídos ({n1},{n2})")

    # hashes de CSP para cada script executável inline
    hashes = []
    for m in re.finditer(r"<script(?P<attrs>[^>]*)>(?P<corpo>.*?)</script>", h, flags=re.S):
        if "src=" in m.group("attrs") or "application/json" in m.group("attrs"):
            continue
        hashes.append("'sha256-" + base64.b64encode(hashlib.sha256(m.group("corpo").encode()).digest()).decode() + "'")
    csp = ("default-src 'none'; script-src " + " ".join(hashes) + "; style-src 'unsafe-inline'; img-src 'self' data: https:; font-src data:; "
           "connect-src 'self'; base-uri 'none'; form-action 'self'; object-src 'none'; frame-src 'none'; worker-src 'none'; upgrade-insecure-requests")
    doc = '<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="' + csp + '">\n' + h.replace('<meta charset="utf-8">', "", 1) + "\n</html>\n"

    # verificações finais
    sem_dados = re.sub(r'<script type="application/json"[^>]*>.*?</script>', "", doc, flags=re.S)
    sem_dados = re.sub(r"data:[a-z/0-9+.-]+;base64,[A-Za-z0-9+/=]+", "data:", sem_dados)
    sem_jsqr = sem_dados.replace(jsqr, "")
    for rotulo, rx in (("login de teste", r'mail==="admin"'), ("CDN de terceiros", r"cdn\.jsdelivr|googleapis|gstatic|cloudflare"), ("handler inline", r"\son(error|load|click)=\""),
                       ("segredo", r"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|ghp_[A-Za-z0-9]{36}|xox[baprs]-|BEGIN [A-Z ]*PRIVATE KEY|sk-[A-Za-z0-9]{20,}|chave-super|TICKETMASTER_API|apikey=")):
        if re.search(rx, sem_jsqr):
            erros.append(f"encontrado no bundle: {rotulo}")
    for bloco in re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', doc, flags=re.S):
        sem_b64 = re.sub(r"data:[a-z/0-9+.-]+;base64,[A-Za-z0-9+/=]+", "", bloco)
        if re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}|[\w.+-]+@[\w-]+\.[a-z]{2,}", sem_b64):
            erros.append("CNPJ/CPF/e-mail encontrado nos dados embutidos")
    if len(doc.encode()) > 15_000_000:
        erros.append("arquivo passa de 15 MB")
    if erros:
        sys.exit("BUILD FALHOU:\n - " + "\n - ".join(erros))
    open(a.saida, "w", encoding="utf-8").write(doc)
    open(a.saida + ".csp.txt", "w").write(csp + "\n")
    print(f"ok: {a.saida} ({len(doc.encode())//1024} KB), {len(hashes)} scripts com hash de CSP" + (" — HOMOLOGAÇÃO (dados pendentes): NÃO PUBLICAR" if (faltando or not a.juridico_revisado) else ""))


if __name__ == "__main__":
    main()
