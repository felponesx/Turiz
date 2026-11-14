import sys
dst=sys.argv[1]; h=open(dst,encoding="utf-8").read()
if "/* ===== IMAGENS DOS LUGARES ===== */" in h: print("já aplicado"); sys.exit(0)
def sub(old,new,count=1):
    global h
    assert h.count(old)==count,(old[:60],h.count(old)); h=h.replace(old,new)
sub('.map(([id,t,nome,cui,lat,lon,end,bairro,hor,tel,site])=>{const bar=t===1;','.map(([id,t,nome,cui,lat,lon,end,bairro,hor,tel,site,src,aprox])=>{const bar=t===1;')
sub('spec:bar?"bares":"gastro",desc:"",dishes:[],tel,site}','spec:bar?"bares":"gastro",desc:"",dishes:[],tel,site,src:src?"receita":"osm",aprox:!!aprox}')
JS=r'''
/* ===== IMAGENS DOS LUGARES ===== */
/* Fotos reais coletadas pela API (site do próprio estabelecimento ou Wikimedia Commons), com licença e crédito. Só as APROVADAS aparecem
   por padrão; as pendentes de revisão aparecem só se você ligar a opção em Configurações. Sem foto real, fica a ilustração padrão. */
const IMGS=(()=>{try{return JSON.parse(document.getElementById("api-imagens").textContent)}catch(x){return{}}})();
const REDES=(()=>{try{return JSON.parse(document.getElementById("api-redes").textContent)}catch(x){return{}}})();
const IMGP_KEY="turiz-imgpend",IMGP={on:(()=>{try{return localStorage.getItem(IMGP_KEY)!=="0"}catch(e){return true}})()};
function plImg(p){const l=IMGS[p.id]||[];return l.find(i=>i[4]==="aprovada")||(IMGP.on?l.find(i=>i[4]==="pendente"):null)||null}
window.plImgFail=img=>{const w=img.parentNode;if(!w)return;const c=w.querySelector(".imgcred");if(c)c.remove();const id=img.getAttribute("data-p"),p=PM[id];img.outerHTML=p?scene(p.scene,p.id,p.hue):""};
function plMedia(p,cred){const i=plImg(p);if(!i)return scene(p.scene,p.id,p.hue);
  const lic=i[1]||"licença não informada",auto=i[2]?i[2]+" · ":"";
  return`<img class="evimg" src="${esc(i[0])}" alt="Foto de ${esc(p.name)}" loading="lazy" decoding="async" referrerpolicy="no-referrer" data-p="${esc(p.id)}" onerror="plImgFail(this)">${cred?`<span class="imgcred">${esc(auto+lic)}${i[4]!=="aprovada"?" · aguardando revisão":""}${i[3]?` · <a href="${esc(i[3])}" target="_blank" rel="noopener noreferrer">fonte</a>`:""}</span>`:""}`}
'''
sub('const PM=Object.fromEntries(P.map(p=>[p.id,p]));','const PM=Object.fromEntries(P.map(p=>[p.id,p]));'+JS)
h=h.replace('${scene(p.scene,p.id,p.hue)}${p.rating==null?""','${plMedia(p)}${p.rating==null?""')
sub('<div class="ph">${scene(p.scene,p.id,p.hue)}</div>','<div class="ph">${plMedia(p)}</div>',count=2)
sub('<div class="hero ph">${scene(p.scene,p.id,p.hue)}<div class="top-actions">','<div class="hero ph">${plMedia(p,true)}<div class="top-actions">')
# 'Sobre': redes sociais + fonte dos dados por origem
sub('${p.site?li("share","Site",','${(REDES[p.id]||[]).map(r=>li("share",r[0]==="instagram"?"Instagram":esc(r[0]),`<a href="${esc(r[1])}" target="_blank" rel="noopener noreferrer">@${esc(r[2]||"perfil")}</a>${r[3]!=="confirmado"?` <span class="exm">provável</span>`:""}`,"")).join("")}${p.site?li("share","Site",')
sub('const srcNote=()=>','const srcNoteP=p=>p.src==="receita"?"Dados do local: Receita Federal (dados abertos) e IBGE (CNEFE). Não guardamos CNPJ, razão social nem sócios."+(p.aprox?" A posição é aproximada (centro do CEP).":""):"";\nconst srcNote=()=>')
sub('<p class="note" style="margin-top:12px">${srcNote()}</p>`;','<p class="note" style="margin-top:12px">${srcNoteP(p)||srcNote()}</p>`;')
# configuração
sub('<h2 style="font-size:1rem;margin:20px 0 8px">Dados de exemplo</h2>','<h2 style="font-size:1rem;margin:20px 0 8px">Fotos dos locais</h2><div class="card pad"><div class="li" style="padding:0;border:0"><span class="grow"><b>Mostrar fotos ainda não aprovadas</b><div class="sub">Fotos coletadas dos sites dos estabelecimentos que aguardam revisão de direitos. Aparecem marcadas como "aguardando revisão".</div></span><button class="switch" role="switch" aria-checked="${IMGP.on}" aria-label="Mostrar fotos não aprovadas" data-act="imgpend"></button></div></div>\n<h2 style="font-size:1rem;margin:20px 0 8px">Dados de exemplo</h2>')
sub('    case"demo":{','    case"imgpend":{IMGP.on=!IMGP.on;try{localStorage.setItem(IMGP_KEY,IMGP.on?"1":"0")}catch(e){}render();break}\n    case"demo":{')
i=h.rindex("</style>"); h=h[:i]+'.imgcred{position:absolute;left:10px;bottom:10px;max-width:calc(100% - 20px);z-index:2;background:rgba(8,28,31,.62);color:#fff;font-size:.68rem;padding:3px 9px;border-radius:99px}.imgcred a{color:#fff;text-decoration:underline}\n'+h[i:]
open(dst,"w",encoding="utf-8").write(h); print("ok")
