import sys
dst=sys.argv[1]; h=open(dst,encoding="utf-8").read()
if "/* ===== FOTOS ILUSTRATIVAS ===== */" in h: print("já aplicado"); sys.exit(0)
def sub(old,new,count=1):
    global h
    assert h.count(old)==count,(old[:70],h.count(old)); h=h.replace(old,new)
JS=r'''
/* ===== FOTOS ILUSTRATIVAS ===== */
/* Com os dados de exemplo ligados, todo bloco sem foto real recebe uma foto ILUSTRATIVA do Wikimedia Commons (licença livre, com autor),
   escolhida pelo tipo/culinária do lugar ou pela categoria do evento. Sempre marcada como "ilustrativa". Foto real tem prioridade. */
const FEX=(()=>{try{return JSON.parse(document.getElementById("api-fotos-ex").textContent)}catch(x){return{}}})();
const TEMA_COZ={"Lanchonete":"lanchonete","Hambúrguer":"hamburguer","Pizzaria":"pizzaria","Japonesa":"japonesa","Cafeteria":"cafeteria","Padaria":"padaria","Churrasco":"churrasco","Carnes":"churrasco","Grelhados":"churrasco","Brasileira":"brasileira","Regional":"brasileira","Italiana":"italiana","Massas":"italiana","Árabe":"arabe","Confeitaria":"doces","Açaí":"acai","Pastelaria":"pastel","Sorveteria":"sorveteria","Frango":"brasileira","Peixes":"brasileira","Frutos do mar":"brasileira"};
const TEMA_NOME=[[/pizz/i,"pizzaria"],[/burg/i,"hamburguer"],[/sushi|temaki|japon/i,"japonesa"],[/caf[eé]|coffee/i,"cafeteria"],[/padaria|panifica|p[aã]es/i,"padaria"],[/a[cç]a[ií]/i,"acai"],[/pastel/i,"pastel"],[/doce|confeit|bolo|brigadeir/i,"doces"],[/churras|grill|steak/i,"churrasco"],[/esfi|[aá]rabe|kebab/i,"arabe"],[/sorvet|gelat/i,"sorveteria"],[/\bbar\b|boteco|choperia|pub\b/i,"bar"],[/lanche|salgad|coxinha/i,"lanchonete"]];
function temaLugar(p){if(p.type==="Bar")return"bar";if(TEMA_COZ[p.cuisine])return TEMA_COZ[p.cuisine];const t=TEMA_NOME.find(([r])=>r.test(p.name));return t?t[1]:"restaurante"}
function temaEvento(e){const c=e.cats||[];if(c.some(x=>catAnc(x).includes("gastronomia")))return"gastronomia_evento";if(c.some(x=>["festas","baladas","djs"].includes(x)))return"festa";if(c.some(x=>catAnc(x).includes("cultura-lazer")))return"cultura";
  if(e.scene==="bar")return"bar";if(e.scene==="food"||e.scene==="house")return"gastronomia_evento";return"show"}
function fotoEx(tema,key){const l=FEX[tema]&&FEX[tema].length?FEX[tema]:(FEX.restaurante||[]);if(!l.length)return null;const f=l[hash("f"+key)%l.length];return[f[0],f[2],f[1],f[3],"ilustrativa"]}
function plFoto(p){return plImg(p)||(DEMO.on?fotoEx(temaLugar(p),p.id):null)}
const ilusTag=`<span class="ilus">foto ilustrativa</span>`;
'''
sub('function plImg(p){',JS+'function plImg(p){')
sub('function plMedia(p,cred){const i=plImg(p);if(!i)return scene(p.scene,p.id,p.hue);','function plMedia(p,cred){const i=plFoto(p);if(!i)return scene(p.scene,p.id,p.hue);')
sub('''${cred?`<span class="imgcred">${esc(auto+lic)}${i[4]!=="aprovada"?" · aguardando revisão":""}''','''${i[4]==="ilustrativa"&&!cred?ilusTag:""}${cred?`<span class="imgcred">${i[4]==="ilustrativa"?"Foto ilustrativa (exemplo) · ":""}${esc(auto+lic)}${i[4]==="pendente"?" · aguardando revisão":""}''')
# eventos: real sem foto e de exemplo
sub('const evMedia=e=>e.real?(e.img?','const evMediaEx=e=>{const f=DEMO.on?fotoEx(temaEvento(e),e.id):null;return f?`<img class="evimg" src="${esc(f[0])}" alt="" loading="lazy" decoding="async">${ilusTag}`:null};\nconst evMedia=e=>(!(e.real&&e.img)&&evMediaEx(e))||(e.real?(e.img?')
# fecha o parêntese extra no fim da expressão de evMedia
i=h.index('const evMedia=e=>(!(e.real&&e.img)&&evMediaEx(e))||'); j=h.index('\n',i)
linha=h[i:j]
assert linha.endswith(';'),linha[-40:]
h=h[:i]+linha[:-1]+');'+h[j:]
i2=h.rindex("</style>")
h=h[:i2]+'.hrow .ilus{left:5px;bottom:5px;font-size:.5rem;padding:1px 5px}\n.ilus{position:absolute;left:10px;bottom:10px;z-index:2;background:rgba(0,0,0,.5);color:#fff;font-size:.62rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase;padding:2px 8px;border-radius:6px}\n'+h[i2:]
open(dst,"w",encoding="utf-8").write(h); print("ok")
