#!/usr/bin/env python3
"""Embute no turiz.html os dados REAIS do repo: lugares (OSM + Receita/IBGE, sem CNPJ), imagens (com licença/crédito), redes sociais e eventos.
Uso: python3 build_api_all.py <data_dir> <turiz.html>"""
import gzip, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_api_data as B
import build_api_eventos as EV

def bloco(html, nome, ident, payload):
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    novo = f'<!--{nome}--><script type="application/json" id="{ident}">{blob}</script><!--/{nome}-->'
    if f"<!--{nome}-->" in html:
        return re.sub(rf"<!--{nome}-->.*?<!--/{nome}-->", lambda m: novo, html, flags=re.S), len(blob)
    assert html.count("<!--/API-DATA-->") == 1
    return html.replace("<!--/API-DATA-->", "<!--/API-DATA-->\n" + novo), len(blob)

def main(pasta, dst):
    osm = json.load(open(f"{pasta}/lugares.json", encoding="utf-8"))
    rec = json.load(gzip.open(f"{pasta}/lugares_receita.json.gz", "rt", encoding="utf-8")) if os.path.exists(f"{pasta}/lugares_receita.json.gz") else []
    rows, chave = [], {}
    for r in osm:
        nome = (r.get("nome") or "").strip()
        if not nome: continue
        rows.append([r["id"], 1 if r["tipo"] == "bar" else 0, nome, B.cuisine(r.get("culinaria")), round(r["lat"], 5), round(r["lon"], 5), (r.get("endereco") or "").strip(),
                     (r.get("bairro") or "").strip(), B.hours(r.get("horario")), B.tel(r.get("telefone")), B.site(r.get("site")), 0, 0])
        chave[(r["fonte"], r["fonte_id"])] = r["id"]
    for r in rec:   # nunca há CNPJ aqui; fonte_id é um hash
        nome = (r.get("nome") or "").strip()
        if not nome or "@" in nome: continue
        rid = "r" + r["fonte_id"]
        rows.append([rid, 1 if r["tipo"] == "bar" else 0, nome, r.get("culinaria") or "", round(r["lat"], 5), round(r["lon"], 5), (r.get("endereco") or "").strip(),
                     (r.get("bairro") or "").strip(), "", "", "", 1, 1 if (r.get("extra") or {}).get("coordenada_aproximada") else 0])
        chave[(r["fonte"], r["fonte_id"])] = rid
    html = open(dst, encoding="utf-8").read()
    html, n1 = bloco(html, "API-DATA", "api-lugares", rows)
    imgs = {}
    for i in json.load(open(f"{pasta}/imagens.json", encoding="utf-8")):
        k = chave.get((i["lugar_fonte"], i["lugar_fonte_id"]))
        if k is None or not re.match(r"^https://[^\s\"'<>]+$", i.get("url") or ""): continue
        imgs.setdefault("api-%s" % k, []).append([i["url"], i.get("licenca", ""), i.get("autor", ""), i.get("creditos_url", ""), i.get("status", "pendente")])
    html, n2 = bloco(html, "API-IMAGENS", "api-imagens", imgs)
    redes = {}
    for r in json.load(open(f"{pasta}/redes_sociais.json", encoding="utf-8")):
        k = chave.get((r["lugar_fonte"], r["lugar_fonte_id"]))
        if k is None or r.get("status") == "rejeitado" or not re.match(r"^https://[^\s\"'<>]+$", r.get("url") or ""): continue
        redes.setdefault("api-%s" % k, []).append([r["rede"], r["url"], r.get("usuario", ""), r.get("status", "provavel")])
    html, n3 = bloco(html, "API-REDES", "api-redes", redes)
    open(dst, "w", encoding="utf-8").write(html)
    print(f"{len(rows)} lugares ({n1//1024} KB; {len(rec)} da Receita), {sum(len(v) for v in imgs.values())} imagens em {len(imgs)} lugares, {sum(len(v) for v in redes.values())} redes em {len(redes)} lugares")
    EV.main(pasta, dst)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
