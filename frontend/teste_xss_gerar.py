"""Gera uma cópia do protótipo com PAYLOADS DE XSS em todos os campos de dados externos, para provar que nada executa."""
import json, re, sys
src, dst = sys.argv[1], sys.argv[2]
h = open(src, encoding="utf-8").read()
P = ['<img src=x onerror=window.__xss=1>', '"><svg onload=window.__xss=1>', "'-window.__xss=1-'", '</script><script>window.__xss=1</script>',
     '<a href=javascript:window.__xss=1>x</a>', '${window.__xss=1}', '`;window.__xss=1;`', '&lt;img src=x onerror=window.__xss=1&gt;']
JS_URL = "javascript:window.__xss=1"
def blob(ident):
    m = re.search(r'(<script type="application/json" id="%s">)(.*?)(</script>)' % ident, h, flags=re.S)
    return m, json.loads(m.group(2).replace("<\\/", "</"))
def put(ident, dados, txt):
    m, _ = blob(ident)
    novo = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return txt[:m.start(2)] + novo + txt[m.end(2):]
import itertools
ciclo = itertools.cycle(P)
def pay(campo="?"): return f'<img src=x onerror=window.__xss=1 data-f="{campo}">'
# lugares: [id,tipo,nome,cui,lat,lon,end,bairro,hor,tel,site,src,aprox]
_, L = blob("api-lugares")
for r in L:
    r[2], r[3], r[6], r[7], r[8], r[9], r[10] = pay("lugar.nome"), pay("lugar.culinaria"), pay("lugar.endereco"), pay("lugar.bairro"), pay("lugar.horario"), pay("lugar.tel"), JS_URL
h = put("api-lugares", L, h)
_, E = blob("api-eventos")
for e in E["itens"]:
    for k in ("t", "ci", "uf", "ln", "ad", "k", "d", "mo"): e[k] = pay("evento."+k)
    e["ar"] = [pay("evento.artista"), pay("evento.artista")]; e["fs"] = [pay("evento.fonte")]; e["tk"] = JS_URL; e["u"] = JS_URL; e["im"] = JS_URL; e["cs"] = [pay("evento.cat")]
h = put("api-eventos", E, h)
_, I = blob("api-imagens")
for k, v in I.items():
    for i in v: i[1], i[2], i[3] = pay("img.licenca"), pay("img.autor"), JS_URL
h = put("api-imagens", I, h)
_, R = blob("api-redes")
for k, v in R.items():
    for r in v: r[0], r[1], r[2] = pay("rede.nome"), JS_URL, pay("rede.usuario")
h = put("api-redes", R, h)
_, C = blob("api-cardapios")
for k, v in C.items():
    for c in v: c[0] = JS_URL; c[1] = pay("card.plataforma"); c[3] = [[pay("card.secao"), pay("card.item"), pay("card.desc"), 1.5]]
h = put("api-cardapios", C, h)
_, F = blob("api-fotos-ex")
for k, v in F.items():
    for f in v: f[1], f[2], f[3] = pay("fex.autor"), pay("fex.licenca"), JS_URL
h = put("api-fotos-ex", F, h)
open(dst, "w", encoding="utf-8").write(h)
print("gerado", dst)
