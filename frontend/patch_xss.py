import sys
dst=sys.argv[1]; h=open(dst,encoding="utf-8").read()
if "/* ===== SEGURANÇA DOS DADOS EXTERNOS ===== */" in h: print("já aplicado"); sys.exit(0)
def sub(a,b,c=1):
    global h
    assert h.count(a)==c,(a[:80],h.count(a)); h=h.replace(a,b)
BLOCO=r'''/* ===== SEGURANÇA DOS DADOS EXTERNOS ===== */
/* Tudo que vem de fora (OpenStreetMap, Receita, sites, APIs de eventos) é tratado como NÃO CONFIÁVEL: (1) o escape na saída é a regra;
   (2) aqui, defesa em profundidade: sem < > nem caracteres de controle; links só http(s); imagens só https ou data:image. */
const sanT=s=>typeof s==="string"?s.replace(/[<>\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g,"").slice(0,3000):s;
const urlSeg=u=>/^https?:\/\/[^\s"'<>`]+$/i.test(u||"")?u:"";
const imgSeg=u=>/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+\/=]+$/.test(u||"")||/^https:\/\/[^\s"'<>`]+$/i.test(u||"")?u:"";
const lerJson=(id,def)=>{try{return JSON.parse(document.getElementById(id).textContent)}catch(x){return def}};
'''
sub('const P=JSON.parse(document.getElementById("api-lugares").textContent).map(([id,t,nome,cui,lat,lon,end,bairro,hor,tel,site,src,aprox])=>{const bar=t===1;',
    BLOCO+'const P=JSON.parse(document.getElementById("api-lugares").textContent).map(([id,t,nome,cui,lat,lon,end,bairro,hor,tel,site,src,aprox])=>{const bar=t===1;nome=sanT(nome);cui=sanT(cui);end=sanT(end);bairro=sanT(bairro);hor=sanT(hor);tel=sanT(tel);site=urlSeg(site);')
sub('const CARD=(()=>{try{return JSON.parse(document.getElementById("api-cardapios").textContent)}catch(x){return{}}})();',
    'const CARD=(()=>{const o=lerJson("api-cardapios",{}),r={};for(const k in o){const l=o[k].map(c=>[urlSeg(c[0]),sanT(c[1]),sanT(c[2]),(c[3]||[]).map(i=>[sanT(i[0]),sanT(i[1]),sanT(i[2]),typeof i[3]==="number"?i[3]:null])]).filter(c=>c[0]);if(l.length)r[k]=l}return r})();')
sub('const IMGS=(()=>{try{return JSON.parse(document.getElementById("api-imagens").textContent)}catch(x){return{}}})();',
    'const IMGS=(()=>{const o=lerJson("api-imagens",{}),r={};for(const k in o){const l=o[k].map(i=>[imgSeg(i[0]),sanT(i[1]),sanT(i[2]),urlSeg(i[3]),i[4]==="aprovada"||i[4]==="pendente"?i[4]:"pendente"]).filter(i=>i[0]);if(l.length)r[k]=l}return r})();')
sub('const REDES=(()=>{try{return JSON.parse(document.getElementById("api-redes").textContent)}catch(x){return{}}})();',
    'const REDES=(()=>{const o=lerJson("api-redes",{}),r={};for(const k in o){const l=o[k].map(x=>[sanT(x[0]),urlSeg(x[1]),sanT(x[2]),sanT(x[3])]).filter(x=>x[1]);if(l.length)r[k]=l}return r})();')
sub('const FEX=(()=>{try{return JSON.parse(document.getElementById("api-fotos-ex").textContent)}catch(x){return{}}})();',
    'const FEX=(()=>{const o=lerJson("api-fotos-ex",{}),r={};for(const k in o){const l=o[k].map(f=>[imgSeg(f[0]),sanT(f[1]),sanT(f[2]),urlSeg(f[3])]).filter(f=>f[0]);if(l.length)r[k]=l}return r})();')
# eventos reais
sub('return{id:"r"+r.i,real:true,name:r.t,kind:r.k,cats:r.cs||[],placeId:pid,',
    'r={...r,t:sanT(r.t),k:sanT(r.k),ln:sanT(r.ln),ad:sanT(r.ad),ci:sanT(r.ci),uf:sanT(r.uf),d:sanT(r.d),mo:sanT(r.mo),ar:(r.ar||[]).map(sanT),fs:(r.fs||[]).map(sanT),cs:(r.cs||[]).map(sanT),fz:sanT(r.fz)};\n  return{id:"r"+r.i,real:true,name:r.t,kind:r.k,cats:r.cs||[],placeId:pid,')
# saída escapada
sub('const tc=p=>p.cuisine&&p.cuisine!==p.type?p.type+" · "+p.cuisine:p.type;','const tc=p=>esc(p.cuisine&&p.cuisine!==p.type?p.type+" · "+p.cuisine:p.type);')
sub('<span class="pill gold">${e.kind}</span>${e.demo?','<span class="pill gold">${esc(e.kind)}</span>${e.demo?')
sub('<span class="avatar">${a[0]}</span><b>${esc(a)}</b>','<span class="avatar">${esc(a[0])}</span><b>${esc(a)}</b>')
sub('<b>${d[0]}</b><div class="sub">${d[2]}</div>','<b>${esc(d[0])}</b><div class="sub">${esc(d[2])}</div>')
sub('${v.name[0]}</span><span class="grow"><div class="row between"><b>${v.name}</b>','${esc(v.name[0])}</span><span class="grow"><div class="row between"><b>${esc(v.name)}</b>')
sub('<button class="chip" aria-pressed="${on}" data-act="${fn}:${k}">${l}</button>','<button class="chip" aria-pressed="${on}" data-act="${fn}:${esc(k)}">${esc(l)}</button>')
sub('data-act="pref:${k}:${esc(i)}">${i}</button>','data-act="pref:${k}:${esc(i)}">${esc(i)}</button>')
sub('feat.rating.toFixed(1)+(feat.cuisine?" · "+feat.cuisine:"")}</span>','feat.rating.toFixed(1)+(feat.cuisine?" · "+esc(feat.cuisine):"")}</span>')
sub('Você gosta de cozinha ${p.cuisine.toLowerCase()}.','Você gosta de cozinha ${esc(p.cuisine.toLowerCase())}.')
sub('parts.push(["Cozinha nova: "+p.cuisine,60]);','parts.push(["Cozinha nova: "+esc(p.cuisine),60]);')
open(dst,"w",encoding="utf-8").write(h); print("ok")
