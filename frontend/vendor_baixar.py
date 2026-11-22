#!/usr/bin/env python3
"""Baixa UMA vez as dependências de front (fontes Inter e Plus Jakarta Sans, e jsQR) para frontend/vendor/, com hash de integridade.
Motivo: nada de CDN/Google Fonts em produção (privacidade: o IP do visitante não vai para terceiros; segurança: sem script externo
que possa ser adulterado; CSP estrita). Rodar pelo workflow 'Vendor do front' (precisa de acesso à internet)."""
import base64
import hashlib
import io
import json
import re
import tarfile
import httpx

UA_MODERNO = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SAIDA = "frontend/vendor"


def sri(dados: bytes) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(dados).digest()).decode()


def main():
    import os
    os.makedirs(f"{SAIDA}/fonts", exist_ok=True)
    meta = {}
    with httpx.Client(timeout=60, follow_redirects=True) as c:
        saida_css = []
        # Inter (texto) e Plus Jakarta Sans (títulos): fontes variáveis, só os subconjuntos latin e latin-ext (português)
        for fam, url_fam in (("inter", "Inter:wght@400..600"), ("plusjakarta", "Plus+Jakarta+Sans:wght@500..700")):
            css = c.get(f"https://fonts.googleapis.com/css2?family={url_fam}&display=swap", headers={"User-Agent": UA_MODERNO}).text
            blocos = re.findall(r"/\*\s*([a-z-]+)\s*\*/\s*(@font-face\s*\{.*?\})", css, flags=re.S)
            for subset, bloco in blocos:
                if subset not in ("latin", "latin-ext"):
                    continue
                url = re.search(r"url\((https://[^)]+\.woff2)\)", bloco).group(1)
                dados = c.get(url).content
                arq = f"{fam}-{subset}.woff2"
                open(f"{SAIDA}/fonts/{arq}", "wb").write(dados)
                meta[f"fonts/{arq}"] = {"sri": sri(dados), "bytes": len(dados)}
                saida_css.append(bloco.replace(url, f"fonts/{arq}"))
        open(f"{SAIDA}/fonts.css", "w", encoding="utf-8").write("\n".join(saida_css))
        tgz = c.get("https://registry.npmjs.org/jsqr/-/jsqr-1.4.0.tgz").content
        with tarfile.open(fileobj=io.BytesIO(tgz)) as t:
            js = t.extractfile("package/dist/jsQR.js").read()
        open(f"{SAIDA}/jsQR.js", "wb").write(js)
        meta["jsQR.js"] = {"sri": sri(js), "bytes": len(js), "versao": "1.4.0", "origem": "registry.npmjs.org/jsqr@1.4.0"}
        # Leaflet (página estática da API): hash para SRI
        for arq in ("leaflet.min.js", "leaflet.min.css"):
            dados = c.get(f"https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/{arq}").content
            meta[arq] = {"sri": sri(dados), "bytes": len(dados), "origem": f"cdnjs leaflet 1.9.4/{arq}"}
    json.dump(meta, open(f"{SAIDA}/INTEGRIDADE.json", "w"), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
