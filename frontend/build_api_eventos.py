#!/usr/bin/env python3
"""Embute os eventos REAIS coletados pela API (data/eventos_v2.json.gz + data/lugares.json do repo) em turiz.html.
Uso: python3 build_api_eventos.py <data_dir> <turiz.html>
Só entram eventos reais (nada de exemplo), ainda não encerrados; cancelados/adiados entram com o status. Sem CNPJ/dados pessoais."""
import gzip, json, re, sys
from datetime import datetime, timedelta, timezone

def main(pasta, dst):
    snap = json.load(gzip.open(f"{pasta}/eventos_v2.json.gz", "rt", encoding="utf-8"))
    lugares = {(l["fonte"], l["fonte_id"]): l["id"] for l in json.load(open(f"{pasta}/lugares.json", encoding="utf-8"))}
    locais = {x["id"]: x for x in snap["locais"]}
    cats = {x["id"]: x for x in snap["categorias"]}
    fontes = {x["slug"]: x["nome"] or x["slug"] for x in snap["fontes"]}
    por_ev = lambda tab, k="evento_id": [(r[k], r) for r in snap.get(tab, [])]
    def agrupa(tab):
        d = {}
        for r in snap.get(tab, []):
            d.setdefault(r["evento_id"], []).append(r)
        return d
    c_l, f_l, a_l = agrupa("categoria_links"), agrupa("fonte_links"), agrupa("artista_links")
    artistas = {x["id"]: x["nome"] for x in snap["artistas"]}
    agora = datetime.now(timezone.utc) - timedelta(hours=3)
    out = []
    for e in snap["eventos"]:
        if e["status"] not in ("agendado", "adiado", "remarcado", "cancelado") or not e.get("inicio"):
            continue
        utc = lambda x: (lambda d: d if d.tzinfo else d.replace(tzinfo=timezone.utc))(datetime.fromisoformat(x))   # datas sem fuso estão em UTC
        ini = utc(e["inicio"])
        fim = utc(e["fim"]) if e.get("fim") else None
        e["inicio"] = ini.isoformat()
        e["fim"] = fim.isoformat() if fim else None
        if ini < agora and not (fim and fim >= agora):
            continue
        L = locais.get(e.get("local_id")) or {}
        cl = sorted(c_l.get(e["id"], []), key=lambda r: not r["primaria"])
        out.append({
            "i": e["id"], "t": e["titulo"], "s": e["status"], "a": e["inicio"], "z": e.get("fim"),
            "ci": L.get("cidade", ""), "uf": L.get("estado", ""), "pa": L.get("pais", ""), "ln": L.get("nome") or e.get("local_nome", ""),
            "ad": L.get("endereco") or e.get("endereco", ""), "la": L.get("lat") if L.get("lat") is not None else e.get("lat"), "lo": L.get("lon") if L.get("lon") is not None else e.get("lon"),
            "cs": [cats[r["categoria_id"]]["slug"] for r in cl], "k": cats[cl[0]["categoria_id"]]["nome"] if cl else "Evento",
            "im": e.get("imagem_url", ""), "p0": e.get("preco_min"), "p1": e.get("preco_max"), "mo": e.get("moeda", ""), "g": bool(e.get("gratuito")),
            "tk": e.get("ingresso_url", ""), "u": e.get("url_oficial") or e.get("url", ""),
            "fs": sorted({fontes.get(r["fonte"], r["fonte"]) for r in f_l.get(e["id"], [])}), "d": (e.get("descricao") or "")[:500],
            "ar": [artistas[r["artista_id"]] for r in sorted(a_l.get(e["id"], []), key=lambda r: r["ordem"])][:8],
            "pl": ("api-%s" % lugares[(e["lugar_fonte"], e["lugar_fonte_id"])]) if e.get("lugar_fonte_id") and (e["lugar_fonte"], e["lugar_fonte_id"]) in lugares else "",
            "fz": e.get("fuso", ""),
        })
    out.sort(key=lambda x: x["a"])
    blob = json.dumps({"gerado": datetime.now(timezone.utc).isoformat(timespec="minutes"), "itens": out}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    block = '<!--API-EVENTOS--><script type="application/json" id="api-eventos">' + blob + '</script><!--/API-EVENTOS-->'
    html = open(dst, encoding="utf-8").read()
    if "<!--API-EVENTOS-->" in html:
        html = re.sub(r"<!--API-EVENTOS-->.*?<!--/API-EVENTOS-->", lambda m: block, html, flags=re.S)
    else:
        assert html.count("<!--/API-DATA-->") == 1
        html = html.replace("<!--/API-DATA-->", "<!--/API-DATA-->\n" + block)
    open(dst, "w", encoding="utf-8").write(html)
    print(f"{len(out)} eventos reais embutidos ({len(blob)//1024} KB)")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
