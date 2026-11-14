#!/usr/bin/env python3
"""Embute o banco da API (data/lugares.json do repo felponesx/Turiz) dentro de turiz.html.

Uso:  python3 build_api_data.py <caminho/lugares.json> <caminho/turiz.html>
Reexecute para atualizar o protótipo quando a API coletar dados novos.
O bloco fica entre <!--API-DATA--> e <!--/API-DATA--> e é lido pelo código do protótipo.
"""
import json, re, sys

CUI = {
 "burger":"Hambúrguer","pizza":"Pizzaria","regional":"Regional","japanese":"Japonesa","coffee_shop":"Cafeteria",
 "italian":"Italiana","sandwich":"Lanchonete","brazilian":"Brasileira","arab":"Árabe","middle_eastern":"Árabe",
 "lebanese":"Árabe","kebab":"Árabe","chinese":"Chinesa","steak_house":"Carnes","sushi":"Japonesa","barbecue":"Churrasco",
 "açaí":"Açaí","acai":"Açaí","juice":"Sucos","tea":"Chás","mexican":"Mexicana","chicken":"Frango","portuguese":"Portuguesa",
 "international":"Internacional","indian":"Indiana","korean":"Coreana","french":"Francesa","pastel":"Pastelaria",
 "poke":"Poke","ice_cream":"Sorveteria","bakery":"Padaria","seafood":"Frutos do mar","fish":"Peixes","vegetarian":"Vegetariana",
 "vegan":"Vegana","german":"Alemã","thai":"Tailandesa","peruvian":"Peruana","spanish":"Espanhola","cake":"Confeitaria",
 "crepe":"Crepes","hot_dog":"Cachorro-quente","salad":"Saladas","coffee":"Cafeteria","pub":"Bar","pasta":"Massas",
 "fast_food":"Fast food","tapas":"Tapas","steak":"Carnes","grill":"Grelhados","bar":"Bar","mediterranean":"Mediterrânea",
}
DAYS = {"Mo":"Seg","Tu":"Ter","We":"Qua","Th":"Qui","Fr":"Sex","Sa":"Sáb","Su":"Dom","PH":"feriados","off":"fechado"}

def cuisine(raw):
    for tok in re.split(r"[;,]", raw or ""):
        k = tok.strip().lower()
        if k in CUI:
            return CUI[k]
    return ""

def hours(raw):
    raw = (raw or "").strip()
    if raw == "24/7":
        return "Aberto 24 horas"
    return re.sub(r"\b(Mo|Tu|We|Th|Fr|Sa|Su|PH|off)\b", lambda m: DAYS[m.group(1)], raw)

def site(raw):
    raw = (raw or "").strip()
    if not raw: return ""
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    return raw if re.match(r"^https?://[^\s<>\"']+$", raw, re.I) else ""

def tel(raw):
    return re.sub(r"[^0-9+() \-]", "", (raw or "")).strip()

def main(src, dst):
    rows = json.load(open(src, encoding="utf-8"))
    out = []
    for r in rows:
        nome = (r.get("nome") or "").strip()
        if not nome:
            continue
        out.append([r["id"], 1 if r["tipo"] == "bar" else 0, nome, cuisine(r.get("culinaria")),
                    round(r["lat"], 5), round(r["lon"], 5), (r.get("endereco") or "").strip(),
                    (r.get("bairro") or "").strip(), hours(r.get("horario")), tel(r.get("telefone")), site(r.get("site"))])
    blob = json.dumps(out, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    block = '<!--API-DATA--><script type="application/json" id="api-lugares">' + blob + '</script><!--/API-DATA-->'
    html = open(dst, encoding="utf-8").read()
    if "<!--API-DATA-->" in html:
        html = re.sub(r"<!--API-DATA-->.*?<!--/API-DATA-->", lambda m: block, html, flags=re.S)
    else:
        marker = '<script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js"></script>'
        assert html.count(marker) == 1, "marcador de insercao nao encontrado"
        html = html.replace(marker, block + "\n" + marker)
    open(dst, "w", encoding="utf-8").write(html)
    print(f"{len(out)} lugares embutidos ({len(blob)//1024} KB)")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
