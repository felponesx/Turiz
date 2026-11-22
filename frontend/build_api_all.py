#!/usr/bin/env python3
"""Embute no turiz.html os dados REAIS do repo: lugares (OSM + Receita/IBGE, sem CNPJ), imagens (com licença/crédito), redes sociais e eventos.
Uso: python3 build_api_all.py <data_dir> <turiz.html>"""
import gzip, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_api_data as B
import build_api_eventos as EV
from embutir import data_uri

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
    rows, chave, vistos = [], {}, set()
    def add(r, src):
        nome = (r.get("nome") or "").strip()
        if not nome or "@" in nome or r.get("lat") is None: return
        k = (r["fonte"], r["fonte_id"])
        if k in vistos: return
        vistos.add(k)
        rid = ("r" + r["fonte_id"]) if r["fonte"] == "receita" else r["id"]
        rec_ = r["fonte"] == "receita"
        rows.append([rid, 1 if r["tipo"] == "bar" else 0, nome, (r.get("culinaria") or "") if rec_ else B.cuisine(r.get("culinaria")), round(r["lat"], 5), round(r["lon"], 5),
                     (r.get("endereco") or "").strip(), (r.get("bairro") or "").strip(), "" if rec_ else B.hours(r.get("horario")), "" if rec_ else B.tel(r.get("telefone")),
                     "" if rec_ else B.site(r.get("site")), 1 if rec_ else 0, 1 if (rec_ and (r.get("extra") or {}).get("coordenada_aproximada")) else 0])
        chave[k] = rid
    for r in osm: add(r, 0)         # lugares.json já traz OSM + Receita (sem CNPJ)
    for r in rec: add(r, 1)         # arquivo gz: só o que ainda não estiver no JSON
    html = open(dst, encoding="utf-8").read()
    html, n1 = bloco(html, "API-DATA", "api-lugares", rows)
    import base64
    idx = json.load(open(f"{pasta}/fotos/indice.json", encoding="utf-8")) if os.path.exists(f"{pasta}/fotos/indice.json") else {}
    imgs = {}
    for i in json.load(open(f"{pasta}/imagens.json", encoding="utf-8")):
        k = chave.get((i["lugar_fonte"], i["lugar_fonte_id"]))
        i["url"] = re.sub(r"^http://", "https://", (i.get("url") or "").strip()).replace(" ", "%20")   # a página é https: imagem http seria bloqueada
        if k is None or i.get("status") == "rejeitada" or not re.match(r"^https://[^\s\"'<>]+$", i["url"]): continue
        th = idx.get(str(i["id"]))
        src = i["url"]
        if th and os.path.exists(f"{pasta}/fotos/{th['arquivo']}"):       # miniatura local embutida: não depende do site de origem nem de CSP
            src = data_uri(f"{pasta}/fotos/{th['arquivo']}")
        imgs.setdefault("api-%s" % k, []).append([src, i.get("licenca", ""), i.get("autor", ""), i.get("creditos_url", ""), i.get("status", "pendente")])
    html, n2 = bloco(html, "API-IMAGENS", "api-imagens", imgs)
    redes = {}
    for r in json.load(open(f"{pasta}/redes_sociais.json", encoding="utf-8")):
        k = chave.get((r["lugar_fonte"], r["lugar_fonte_id"]))
        if k is None or r.get("status") == "rejeitado" or not re.match(r"^https://[^\s\"'<>]+$", r.get("url") or ""): continue
        redes.setdefault("api-%s" % k, []).append([r["rede"], r["url"], r.get("usuario", ""), r.get("status", "provavel")])
    html, n3 = bloco(html, "API-REDES", "api-redes", redes)
    card = {}
    pc = f"{pasta}/cardapios.json"
    if os.path.exists(pc):
        for c in json.load(open(pc, encoding="utf-8")):
            k = chave.get((c["lugar_fonte"], c["lugar_fonte_id"]))
            if k is None or c.get("status") == "rejeitado" or not re.match(r"^https?://[^\s\"'<>]+$", c.get("url") or ""): continue
            card.setdefault("api-%s" % k, []).append([c["url"], c.get("plataforma", ""), c.get("status", "provavel"), [[i.get("secao", ""), i.get("nome", ""), i.get("descricao", ""), i.get("preco")] for i in (c.get("itens") or [])]])
    html, n4 = bloco(html, "API-CARDAPIOS", "api-cardapios", card)
    fex = {}
    pf = f"{pasta}/fotos_exemplo/indice.json"
    desc = set(json.load(open(f"{pasta}/fotos_exemplo/descartar.json"))) if os.path.exists(f"{pasta}/fotos_exemplo/descartar.json") else set()
    if os.path.exists(pf):
        for tema, lista in json.load(open(pf, encoding="utf-8")).items():
            for f in lista:
                a = f"{pasta}/fotos_exemplo/{f['arquivo']}"
                if os.path.exists(a) and f["arquivo"] not in desc:
                    fex.setdefault(tema, []).append([data_uri(a, 400, 250, 58), f.get("autor", ""), f.get("licenca", ""), f.get("pagina", "")])
    html, n5 = bloco(html, "API-FOTOS-EX", "api-fotos-ex", fex)
    print(f"{sum(len(v) for v in fex.values())} fotos ilustrativas em {len(fex)} temas ({n5//1024} KB)")
    open(dst, "w", encoding="utf-8").write(html)
    print(f"{sum(len(v) for v in card.values())} cardápios em {len(card)} lugares;", f"{len(rows)} lugares ({n1//1024} KB; {len(rec)} da Receita), {sum(len(v) for v in imgs.values())} imagens em {len(imgs)} lugares, {sum(len(v) for v in redes.values())} redes em {len(redes)} lugares")
    EV.main(pasta, dst)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
