import sys
dst=sys.argv[1]; h=open(dst,encoding="utf-8").read()
if "/* ===== CARDAPIOS REAIS ===== */" in h: print("já aplicado"); sys.exit(0)
def sub(old,new,count=1):
    global h
    assert h.count(old)==count,(old[:70],h.count(old)); h=h.replace(old,new)
JS=r'''
/* ===== CARDAPIOS REAIS ===== */
/* Cardápio OFICIAL achado pelo bot no site do próprio estabelecimento: itens (quando o site publica em schema.org) ou o link da plataforma/PDF. */
const CARD=(()=>{try{return JSON.parse(document.getElementById("api-cardapios").textContent)}catch(x){return{}}})();
const PLAT={goomer:"Goomer",menudino:"MenuDino",anotaai:"Anota Aí",cardapioweb:"Cardápio Web",ifood:"iFood",pdf:"PDF",imagem:"Imagem",proprio:"Site do local",outro:"Cardápio online"};
function cardReal(p){const l=CARD[p.id];if(!l)return"";
  const itens=l.flatMap(c=>c[3]||[]);
  const links=l.map(c=>`<a class="btn soft" href="${esc(c[0])}" target="_blank" rel="noopener noreferrer">${ic("fork")} ${esc(PLAT[c[1]]||"Cardápio")}${c[2]!=="confirmado"?" (provável)":""}</a>`).join("");
  const sec={};itens.forEach(i=>{(sec[i[0]||"Cardápio"]=sec[i[0]||"Cardápio"]||[]).push(i)});
  return`<div class="sec" style="margin-top:0"><div class="row wrap" style="gap:8px">${links}</div>${Object.entries(sec).map(([s,l2])=>`<h2 style="font-size:1rem;margin:16px 0 8px">${esc(s)}</h2><div class="list card">${l2.map(i=>`<div class="li"><span class="grow"><b>${esc(i[1])}</b>${i[2]?`<div class="sub">${esc(i[2])}</div>`:""}</span>${i[3]!=null?`<b style="font-variant-numeric:tabular-nums">${brl(i[3]).replace(",00","")}</b>`:""}</div>`).join("")}</div>`).join("")}<p class="note" style="margin-top:8px">Cardápio oficial do estabelecimento; confirme preços no local.</p></div>`}
'''
sub('/* ===== IMAGENS DOS LUGARES ===== */',JS+'/* ===== IMAGENS DOS LUGARES ===== */')
sub('else if(t==="cardapio")body=p.dishes.length?','else if(t==="cardapio")body=cardReal(p)+(p.dishes.length?')
sub('</p>`:`<div class="card state"><div class="big brand">${ic("fork")}</div><h3>Cardápio ainda não disponível</h3><p class="sub">Este local ainda não tem pratos cadastrados.</p></div>`;','</p>`:(CARD[p.id]?"":`<div class="card state"><div class="big brand">${ic("fork")}</div><h3>Cardápio ainda não disponível</h3><p class="sub">Este local ainda não tem pratos cadastrados.</p></div>`));')
open(dst,"w",encoding="utf-8").write(h);print("ok")
