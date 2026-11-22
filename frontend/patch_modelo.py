#!/usr/bin/env python3
"""Layout das telas no estilo do modelo enviado pelo dono (Início, Explorar, Festas e Perfil), com os NOSSOS dados reais.

O que vem do modelo: cabeçalho com localização e contador de favoritos, cartão de destaque 4:5 com degradê, carrosséis de fotos com etiqueta de
categoria, lista com miniaturas, grade de 2 colunas no Explorar, agenda de eventos em linhas (com preço e "Salvar"), perfil com faixa
verde-escuro ("Passaporte urbano") e métricas separadas por linhas finas; filtros em pílulas; tipografia só Inter; ícones de traço 1,5;
aviso com ponto de areia; painel de 14 px; rota do mapa em areia animada; abas com os ícones do modelo.
O que NÃO vem do modelo: os lugares, notas, preços, fotos e eventos inventados dele. Aqui tudo continua sendo o nosso dado
(real, ou rotulado como exemplo). O nosso mapa (no topo do Explorar) e a aba Favoritos ficam como estão.
Idempotente (marcador). Roda depois de patch_carvao.py e patch_splash.py. Uso: python3 patch_modelo.py turiz.html"""
import re
import sys

MARCA = "/* ===== MODELO: TELAS ===== */"

CSS = MARCA + r"""
/* Tokens da versão 2 do modelo: superfície #1C1F1D, superfície alternativa #161917, mapa #0E100F; só Inter */
:root:not([data-theme="light"]),:root[data-theme="dark"]{--surface:#1C1F1D;--surface-2:#161917;--line:#2B2F2D;--map-land:#0E100F;--map-block:#161917;--scrim:rgba(0,0,0,.75);
  --font-display:'Inter',system-ui,sans-serif}
:root[data-theme="light"]{--font-display:'Inter',system-ui,sans-serif}
h1,h2,h3,.top h1,.stat b,.kpis b{font-weight:600;letter-spacing:-.02em}
.i{stroke-width:1.5}
.iconbtn{border-radius:10px;width:38px;height:38px}
.chip{border-radius:999px}
button.li:hover,.li[data-go]:hover{background:color-mix(in srgb,var(--ink) 5%,var(--surface))}
#sheet .panel{border-radius:14px 14px 0 0}
@media (min-width:720px){#sheet .panel{border-radius:14px}}
#toast::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--brand);margin-right:9px;vertical-align:middle}
.tile,.evtile{background:linear-gradient(135deg,var(--brand-soft),var(--bg))}
/* rota do mapa em areia, tracejada e animada (parada quando a pessoa pede menos movimento) */
.map .routebase{stroke:var(--bg)}
.map .route{stroke:var(--brand);stroke-dasharray:10 10;animation:m-rota 1.1s linear infinite}
@keyframes m-rota{to{stroke-dashoffset:-20}}

/* ---- peças compartilhadas ---- */
.m-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}
.m-loc{display:flex;align-items:center;gap:6px;font-size:.78rem;font-weight:500;color:var(--ink)}
.m-loc .i,.m-ib .i{width:1.1em;height:1.1em;color:var(--brand)}
.m-ib{height:36px;min-width:36px;padding:0 10px;border-radius:10px;border:1px solid var(--line);background:var(--surface);color:var(--ink);display:inline-flex;align-items:center;justify-content:center;gap:6px;font-size:.72rem;font-weight:600}
.m-h1{font-size:1.3rem;line-height:1.22}
.m-sec{margin-top:26px}
.m-sh{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:12px}
.m-sh h3{font-size:.9rem}
.m-sh p{font-size:.7rem;color:var(--ink-2);margin-top:2px}
.m-lk{background:none;border:0;padding:4px 0;color:var(--brand);font-size:.75rem;font-weight:500;display:inline-flex;gap:6px;align-items:center}
.m-meta{font-size:.7rem;color:var(--ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
.m-ph{border-radius:10px;margin-bottom:8px;background:var(--brand-soft)}
.m-ph .heart{width:28px;height:28px;top:6px;right:6px;border-radius:50%}
.m-ph .heart .i{width:14px;height:14px}
.m-tag{position:absolute;left:8px;top:8px;z-index:2;padding:2px 7px;border-radius:6px;background:rgba(17,19,18,.86);color:#F2EFE9;font-size:.62rem;font-weight:500;max-width:calc(100% - 50px);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.m-tcard{display:block;cursor:pointer;width:160px;flex:none;min-width:0}
.m-tcard h4{font-size:.78rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transition:color var(--mo-base) var(--mo-out)}
.m-grid .m-tcard{width:auto}
.m-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px 14px}
@media (min-width:720px){.m-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (min-width:1100px){.xsplit .m-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.m-count{display:flex;justify-content:space-between;align-items:center;font-size:.72rem;color:var(--ink-2);margin:2px 0 12px}
.m-chips{display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;padding-bottom:2px}
.m-chips::-webkit-scrollbar{display:none}
.m-chips .chip{flex:none;padding:7px 14px;font-size:.78rem;font-weight:500;color:var(--ink-2)}
.m-chips .chip .n{opacity:1;margin-left:6px}
.m-chips .chip[aria-pressed="true"]{background:var(--brand);border-color:var(--brand);color:var(--brand-ink);font-weight:600}
.m-nota{font-size:.7rem;font-weight:500;white-space:nowrap}
.m-sand{font-size:.7rem;color:var(--brand);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
/* destaque */
.m-hero{position:relative;display:block;border-radius:12px;overflow:hidden;background:var(--surface);border:1px solid var(--line);cursor:pointer;color:#F2EFE9}
.m-hero .ph{aspect-ratio:4/5;max-height:560px;width:100%;border-radius:0;margin:0}
.m-hero-fade{position:absolute;inset:0;background:linear-gradient(to top,#111312 0%,rgba(17,19,18,.5) 42%,rgba(17,19,18,0) 75%);pointer-events:none}
.m-hero-top{position:absolute;top:14px;left:14px;right:14px;display:flex;justify-content:space-between;align-items:center;gap:8px;pointer-events:none}
.m-hx{padding:4px 10px;border-radius:8px;background:#C8B288;color:#111312;font-size:.7rem;font-weight:600}
.m-hd{padding:4px 8px;border-radius:8px;background:rgba(17,19,18,.86);border:1px solid rgba(242,239,233,.1);color:#F2EFE9;font-size:.7rem;font-weight:500}
.m-hero-b{position:absolute;left:0;right:0;bottom:0;padding:16px 64px 16px 16px}
.m-hero-k{font-size:.7rem;color:#C8B288;font-weight:500;margin-bottom:4px}
.m-hero-b h2{font-size:1.15rem;line-height:1.25;color:#F2EFE9}
.m-hero-d{font-size:.75rem;color:rgba(242,239,233,.85);margin-top:4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.m-hero .heart{top:auto;bottom:16px;right:14px}
@media (min-width:720px){.m-hero .ph{aspect-ratio:16/8}}
/* lista com miniaturas */
.m-list{border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.m-row{display:flex;gap:12px;align-items:center;padding:12px 0;cursor:pointer;border-top:1px solid var(--line);min-width:0}
.m-row:first-child{border-top:0}
.m-thumb{width:56px;height:56px;border-radius:8px;flex:none;margin:0}
.m-row .grow{min-width:0}
.m-row-t{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.m-row h4{font-size:.78rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media (min-width:900px){.m-list{display:grid;grid-template-columns:1fr 1fr;column-gap:36px}.m-row:nth-child(2){border-top:0}}
/* agenda de eventos */
.m-agenda{border-top:1px solid var(--line)}
.m-ev{display:flex;gap:14px;align-items:center;padding:14px 0;border-bottom:1px solid var(--line);cursor:pointer;min-width:0}
.m-ev-th{width:64px;height:64px;border-radius:8px;flex:none;margin:0}
.m-ev-th .ilus,.m-thumb .ilus{left:3px;right:3px;bottom:3px;font-size:.42rem;padding:1px 2px;letter-spacing:0;line-height:1.1;text-align:center}
.m-ev .grow{min-width:0}
.m-ev-t{font-size:.7rem;color:var(--brand);font-weight:500;font-variant-numeric:tabular-nums}
.m-ev h4{font-size:.78rem;font-weight:600;line-height:1.3;margin-top:2px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.m-ev-r{display:grid;justify-items:end;gap:4px;flex:none}
.m-price{padding:4px 10px;border-radius:8px;font-size:.68rem;font-weight:600;border:1px solid var(--line);background:var(--surface);white-space:nowrap;max-width:132px;overflow:hidden;text-overflow:ellipsis}
.m-price.free{background:var(--brand-soft);color:var(--brand);border-color:color-mix(in srgb,var(--brand) 28%,transparent)}
.m-save{display:inline-flex;gap:4px;align-items:center;border:0;background:none;color:var(--ink-2);font-size:.66rem;font-weight:500;padding:5px 2px}
.m-save .i{width:12px;height:12px}
.m-save[aria-pressed="true"]{color:var(--brand)}
.m-save[aria-pressed="true"] .i{fill:currentColor}
@media (min-width:900px){.m-agenda{display:grid;grid-template-columns:1fr 1fr;column-gap:40px}}
.m-phead{padding-bottom:14px;margin-bottom:6px}
.m-phead .row.between{align-items:baseline}
/* perfil */
.m-pf{background:var(--dark-grad);color:#F2EFE9;border:1px solid rgba(200,178,136,.22);border-radius:12px;padding:16px}
.m-pf-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.m-up{font-size:.68rem;font-weight:500;letter-spacing:.09em;text-transform:uppercase;color:#C8B288}
.m-pf .m-lk{color:#F2EFE9}
.m-pf .m-lk .i{width:1em;height:1em;color:#C8B288}
.m-pf-id{display:flex;align-items:center;justify-content:space-between;gap:12px}
.m-av{width:56px;height:56px;border-radius:50%;flex:none;background:rgba(242,239,233,.1);color:#F2EFE9;border:1px solid rgba(200,178,136,.45);display:grid;place-items:center;font:600 1.2rem var(--font-display)}
.m-pf h1{font-size:1.1rem;line-height:1.2;color:#F2EFE9;overflow:hidden;text-overflow:ellipsis}
.m-pf .sub{color:rgba(242,239,233,.78);font-size:.75rem;margin-top:2px}
.m-lvl{padding:4px 10px;border-radius:8px;background:rgba(17,19,18,.82);border:1px solid rgba(200,178,136,.32);color:#C8B288;font-size:.75rem;font-weight:600;white-space:nowrap}
.m-xp{margin-top:16px;padding:14px;border-radius:10px;background:rgba(17,19,18,.7);border:1px solid rgba(242,239,233,.08);font-size:.75rem}
.m-xp .between{gap:10px}
.m-xp b{color:#C8B288;font-variant-numeric:tabular-nums}
.m-bar{height:6px;border-radius:99px;background:rgba(242,239,233,.14);overflow:hidden;margin-top:8px}
.m-bar i{display:block;height:100%;background:#C8B288;border-radius:99px;transition:width .5s var(--mo-out)}
.m-xp .note{color:rgba(242,239,233,.78);margin-top:8px}
.m-metrics{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid var(--line);border-radius:12px;background:var(--surface-2);margin-top:12px}
.m-metrics>div{padding:14px 6px;text-align:center}
.m-metrics>div+div{border-left:1px solid var(--line)}
.m-metrics b{display:block;font-size:1rem;font-weight:600;font-variant-numeric:tabular-nums}
.m-metrics span{font-size:.7rem;color:var(--ink-2)}
.m-xr{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid var(--line)}
.m-xr b{font-size:.78rem;font-weight:600;display:block}
.m-xr small{font-size:.7rem;color:var(--ink-2)}
.m-xr .m-v{font-size:.78rem;font-weight:600;color:var(--brand);white-space:nowrap}
.m-xr .m-v.pend{color:var(--warn)}
/* categorias: uma linha só, em 4 colunas iguais que cabem em qualquer celular */
.m-cats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
.m-cats .chip{min-width:0;padding:8px 0;font-size:.7rem;font-weight:500;color:var(--ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:center}
.m-cats .chip[aria-pressed="true"]{background:var(--brand);border-color:var(--brand);color:var(--brand-ink);font-weight:600}
@media (min-width:720px){.m-cats{grid-template-columns:repeat(4,max-content);justify-content:start;gap:8px}.m-cats .chip{padding:7px 14px;font-size:.78rem}}
/* abas de período (e de outras telas): colunas iguais; o texto quebra dentro da aba em vez de sair da tela */
.evfilters .m-sel{position:relative;display:inline-flex;flex:none}
.evfilters .m-sel select{appearance:none;-webkit-appearance:none;border:1px solid var(--line);background:var(--surface);color:var(--ink);box-shadow:none;border-radius:999px;height:auto;min-height:0;font:500 .78rem var(--font-body);padding:8px 30px 8px 14px;max-width:none}
.evfilters .m-sel select:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
.evfilters .m-sel .i{position:absolute;right:11px;top:50%;transform:translateY(-50%);width:14px;height:14px;pointer-events:none;color:var(--ink-2)}
.tabs.seg{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);overflow:visible;gap:2px}
.tabs.seg>button{min-width:0;white-space:normal;line-height:1.15;padding:9px 4px;font-size:.78rem;text-align:center}
"""

HELPERS = r'''
/* ---- peças do layout do modelo (usam só os dados do próprio app) ---- */
const GRUPO_CURTO={musica_entretenimento:"Música",gastronomia:"Gastronomia",cultura_lazer:"Cultura"};
const mPreco=p=>p.price?"$".repeat(Math.min(4,+p.price||0)):"";
const mNotaTxt=p=>p.rating==null?"":"★ "+p.rating.toFixed(1).replace(".",",");
const mMeta=p=>[esc(p.region||p.cuisine||""),mPreco(p),mNotaTxt(p)].filter(Boolean).join(" • ");
const mKm=p=>p.dist.toFixed(1).replace(".",",")+" km";
const mNota=p=>p.rating==null?"":`<span class="m-nota"><span aria-hidden="true">★</span> ${p.rating.toFixed(1).replace(".",",")}<span class="sr"> de 5</span></span>`;
const mCard=(p,r)=>`<article class="m-tcard" data-go="place:${p.id}" tabindex="0" role="link"><div class="ph m-ph" style="aspect-ratio:${r}">${plMedia(p)}<span class="m-tag">${esc(p.type||"Lugar")}</span>${heart(favKey("p",p.id))}</div><h4>${esc(p.name)}</h4><p class="m-meta">${mMeta(p)||esc(p.type||"")}</p></article>`;
const mRow=p=>`<article class="m-row" data-go="place:${p.id}" tabindex="0" role="link"><div class="ph m-thumb">${plMedia(p)}</div><div class="grow"><div class="m-row-t"><h4>${esc(p.name)}</h4>${mNota(p)}</div><p class="m-meta">${esc(p.type||"")}${p.region?" • "+esc(p.region):""} • ${mKm(p)}</p>${p.cuisine?`<p class="m-sand">${esc(p.cuisine)}${mPreco(p)?" • "+mPreco(p):""}</p>`:""}</div></article>`;
const mEvCard=e=>{const l=evLoc(e);return`<article class="m-tcard" data-go="event:${e.id}" tabindex="0" role="link"><div class="ph m-ph" style="aspect-ratio:4/3.4">${evMedia(e)}<span class="m-tag">${esc(evDate(e))}</span>${heart(favKey("e",e.id))}</div><h4>${esc(e.name)}</h4><p class="m-meta">${esc(l.name)}${evPrice(e)?" • "+esc(evPrice(e)):""}</p>${evStatus(e)}</article>`};
const mEvRow=e=>{const l=evLoc(e),pr=evPrice(e),k=favKey("e",e.id),on=isFav(k);return`<article class="m-ev" data-go="event:${e.id}" tabindex="0" role="link"><div class="ph m-ev-th">${evMedia(e)}</div><div class="grow"><p class="m-ev-t">${esc(evDate(e))}</p><h4>${esc(e.name)}</h4><p class="m-meta">${esc(l.name)}${l.hood?" • "+esc(l.hood):""}</p>${evStatus(e)}${e.demo?`<span class="exm">exemplo</span>`:""}</div><div class="m-ev-r">${pr?`<span class="m-price${e.free?" free":""}">${esc(pr)}</span>`:""}<button class="m-save" data-act="fav:${k}" aria-pressed="${on}" aria-label="${on?"Remover dos favoritos":"Salvar nos favoritos"}">${ic("heart")}<span>${on?"Salvo":"Salvar"}</span></button></div></article>`};
const mNear=()=>{if(!S._near||S._nearN!==P.length){S._nearN=P.length;S._near=[...P].sort((a,b)=>a.dist-b.dist).slice(0,60)}return S._near};
'''

HOME = r'''
V.home=()=>{const feat=P.find(p=>plImg(p)&&p.dist<30)||P.filter(p=>p.type==="Restaurante"&&p.cuisine&&p.hours!=="Horário não informado").slice(0,40).sort((a,b)=>(b.rating||0)-(a.rating||0))[0]||P[0],today=E.filter(e=>e.day==="hoje"),vis=visited(),disc=[...P.filter(p=>plImg(p)&&p.dist<60&&p.id!==feat.id).slice(0,3),...P.filter(p=>!vis.has(p.id)&&p.id!==feat.id&&!plImg(p)).slice(0,4)];
const cats=[["Restaurantes","fork","explore:Restaurante"],["Bares","glass","explore:Bar"],["Festas","star","go:parties"],["Eventos","ticket","go:parties:fds"],["Pizzarias","fork","explore:cuisine:Pizzaria"]];
const usados=new Set([feat.id,...disc.map(p=>p.id)]),perto=mNear().filter(p=>!usados.has(p.id)).slice(0,6);
return`<div class="m-top"><p class="m-loc">${ic("pin")}<span>São Paulo, SP</span></p><div class="row" style="gap:8px"><button class="m-ib" data-go="notifs" aria-label="Notificações">${ic("bell")}</button><button class="m-ib" data-go="favs" aria-label="Favoritos: ${S.fav.size}">${ic("heart")}<b>${S.fav.size}</b></button></div></div>
<h1 class="m-h1">Olá, ${esc(primeiroNome())}!</h1><p class="sub" style="margin:2px 0 14px">Qual será o seu próximo destino?</p>
<form class="search" id="homeq" role="search">${ic("search")}<input id="hq" placeholder="Buscar restaurantes, pratos, eventos" aria-label="Buscar"></form>
<p class="kpi-line" style="margin-top:12px">${num(KPI.all)} lugares · ${num(KPI.rest)} restaurantes · ${num(KPI.bar)} bares${DEMO.on?" · <span class=\"exm\">exemplo</span> notas e preços":""}</p>
<article class="m-hero" data-go="place:${feat.id}" tabindex="0" role="link"><div class="ph">${plMedia(feat)}</div><div class="m-hero-fade"></div><div class="m-hero-top"><span class="m-hx">Perto de você</span>${feat.rating==null?"":`<span class="m-hd"><span aria-hidden="true">★</span> ${feat.rating.toFixed(1).replace(".",",")}<span class="sr"> de 5</span></span>`}</div><div class="m-hero-b"><p class="m-hero-k">${esc(feat.type||"")}${feat.region?" • "+esc(feat.region):""} • ${mKm(feat)}</p><h2>${esc(feat.name)}</h2>${feat.addr?`<p class="m-hero-d">${esc(feat.addr)}</p>`:""}</div>${heart(favKey("p",feat.id))}</article>
<div class="cats">${cats.map(([l,i,g])=>`<button class="cat" data-act="cat:${g}"><span class="c">${ic(i)}</span>${l}</button>`).join("")}</div>
<section class="m-sec"><div class="m-sh"><h3>Explorar por cozinha</h3></div><div class="hscroll m-chips">${CUISINES.map(c=>`<button class="chip" data-act="cat:explore:cuisine:${esc(c)}">${esc(c)}<span class="n">${num(CUI_N[c])}</span></button>`).join("")}</div></section>
<section class="m-sec"><div class="m-sh"><h3>O que está acontecendo hoje</h3><button class="m-lk" data-go="parties">Ver tudo</button></div>${today.length?`<div class="hscroll">${today.map(mEvCard).join("")}</div>`:`<div class="card pad row" style="gap:14px"><span class="ico">${ic("star")}</span><div><b>Nenhum evento para hoje</b><div class="sub">Veja os próximos na aba Festas.</div></div></div>`}</section>
<section class="m-sec"><div class="m-sh"><h3>Descubra algo novo</h3><button class="m-lk" data-go="foryou">Para você</button></div><div class="hscroll">${disc.map(p=>mCard(p,"4/4.6")).join("")}</div></section>
<section class="m-sec"><div class="m-sh"><div><h3>Mais perto de você</h3><p>Lugares a poucos passos da Praça da Sé (posição simulada)</p></div></div><div class="m-list">${perto.map(mRow).join("")}</div></section>`};
'''

EXPLORE = r'''
V.explore=()=>{const l=filtered(),f=S.filt,n=filtCount(),sig=JSON.stringify([f.q,[...f.types],[...f.prices],f.maxDist,f.minRating,[...f.cuisines]]);if(S.xlsig!==sig){S.xlsig=sig;S.xl=30}
const shown=l.slice(0,S.xl),pins=shown.slice(0,15),pr=fitProj([USER,...pins.map(p=>[p.lat,p.lon])]),mp=pins.map(p=>{const[x,y]=pr(p.lat,p.lon);return{...p,x,y}}),me=pr(USER[0],USER[1]);
const chips=[["Restaurante","Restaurantes","qtype"],["Bar","Bares","qtype"],...CUISINES.slice(0,6).map(c=>[c,c,"qcui"])];
return`<div class="top"><h1>Explorar</h1><span class="proto">OpenStreetMap · Receita/IBGE</span></div>
<div class="row"><form class="search grow" id="exq" role="search">${ic("search")}<input id="xq" value="${esc(f.q)}" placeholder="Buscar nesta área" aria-label="Buscar"></form><button class="iconbtn" data-act="filters" aria-label="Filtros" style="position:relative">${ic("sliders")}${n?`<span class="pill" style="position:absolute;top:-6px;right:-6px;background:var(--brand);color:var(--brand-ink);padding:1px 6px">${n}</span>`:""}</button></div>
<div class="m-chips" style="margin:12px 0" role="group" aria-label="Filtros rápidos"><button class="chip" aria-pressed="${!f.types.size&&!f.cuisines.size}" data-act="qall">Todos</button>${chips.map(([k,t,a])=>`<button class="chip" aria-pressed="${a==="qtype"?f.types.has(k):f.cuisines.has(k)}" data-act="${a}:${esc(k)}">${esc(t)}</button>`).join("")}</div>
${(()=>{const q=(f.q||"").trim();if(q.length<3)return"";const r=evFilter(E,evNL(q).f).slice(0,8);if(!r.length||!evNL(q).info.length)return"";return`<div style="margin-bottom:14px"><header class="row between"><h2 style="font-size:1.05rem">Eventos</h2><button class="link" data-act="pq:${esc(q)}">Ver todos</button></header><div class="hscroll" style="margin-top:8px">${r.map(mEvCard).join("")}</div></div>`})()}<div class="xsplit"><div class="map xmap">${mapSVG(mp,{me})}</div>
<div><div class="m-count"><span>${num(l.length)} ${l.length===1?"local encontrado":"locais encontrados"}${mp.length?` · mapa com os ${mp.length} mais próximos`:""}</span></div>${l.length?`<div class="m-grid">${shown.map(p=>mCard(p,"4/4.8")).join("")}</div>`:`<div class="card state"><div class="big brand">${ic("search")}</div><h3>Nada por aqui com esses filtros</h3><p class="sub">Tente ampliar a distância ou limpar algum filtro.</p><button class="btn soft" data-act="clearfilt">Limpar filtros</button></div>`}${l.length>shown.length?`<button class="btn soft block" style="margin-top:18px" data-act="more">Mostrar mais (${num(l.length-shown.length)} restantes)</button>`:""}<p class="note" style="margin-top:14px">© colaboradores do OpenStreetMap. Distâncias em linha reta a partir da Praça da Sé (posição simulada).${DEMO.on?" Notas e preços são de exemplo.":""}</p></div></div>`};

'''

PARTIES = r'''
V.parties=()=>{const t=S.tab.parties,p=S.pf,nl=p.q.trim()?evNL(p.q):{f:{},info:[]},f={...nl.f};
const reais=E.filter(e=>e.real),temData=f.de!=null||f.ate!=null;
if(p.cidade)f.cidade=p.cidade;if(p.g)f.grupo=p.g;if(p.tipo)f.tipo=p.tipo;if(p.preco==="free")f.gratuito=true;
let l=evFilter(E,f);if(!temData&&t!=="prox")l=l.filter(e=>e.day===t);
if(p.preco==="pago")l=l.filter(e=>!e.free&&e.price!=null&&(!p.maxp||e.price<=+p.maxp));
const cidades=Object.entries(reais.reduce((o,e)=>(e.cidade&&(o[e.cidade]=(o[e.cidade]||0)+1),o),{})).sort((a,b)=>b[1]-a[1]).slice(0,40);
const temTipo=reais.some(e=>e.placeId),n=l.length,vis=l.slice(0,S.pn);
const atualiz=REAL.gerado?new Date(REAL.gerado).toLocaleDateString("pt-BR"):"";
return`<div class="m-phead"><div class="row between"><h1 class="m-h1">Festas</h1><span class="m-sand">${reais.length?"Eventos reais"+(DEMO.on?" + exemplos":""):"Dados de exemplo"}</span></div>
<p class="sub" style="margin:4px 0 14px">Shows, festas, gastronomia e cultura${atualiz?` · dados atualizados em ${atualiz}`:""}.</p>
<form class="search" id="pqf" role="search">${ic("search")}<input id="pq" value="${esc(p.q)}" placeholder="Ex.: shows hoje em São Paulo · festas no fim de semana" aria-label="Buscar eventos"></form>
${nl.info.length?`<p class="evinterp" style="margin-top:8px">Entendi: <b>${nl.info.map(esc).join(" · ")}</b> <button class="link" data-act="pfclear">limpar</button></p>`:""}</div>
${temData?"":segs("parties",[["hoje","Hoje"],["amanha","Amanhã"],["fds","Fim de semana"],["prox","Próximos"]])}
<div class="evfilters"><div class="m-cats" role="group" aria-label="Categorias"><button class="chip" aria-pressed="${!p.g}" data-act="pf:g:">Tudo</button>${GRUPOS.map(([k,n2])=>`<button class="chip" aria-pressed="${p.g===k}" title="${esc(n2)}" data-act="pf:g:${k}">${GRUPO_CURTO[k]||n2}</button>`).join("")}</div>
<div class="evrow m-chips">${cidades.length>1?`<select id="pcity" aria-label="Cidade"><option value="">Todas as cidades</option>${cidades.map(([c,k])=>`<option value="${esc(c)}"${p.cidade===c?" selected":""}>${esc(c)} (${k})</option>`).join("")}</select>`:""}
<button class="chip" aria-pressed="${p.preco==="free"}" data-act="pf:preco:free">Gratuitos</button><button class="chip" aria-pressed="${p.preco==="pago"}" data-act="pf:preco:pago">Pagos</button>${p.preco==="pago"?`<label class="m-sel"><select id="pmax" aria-label="Preço máximo">${[["","Sem limite"],["50","Até R$ 50"],["100","Até R$ 100"],["200","Até R$ 200"],["500","Até R$ 500"]].map(([v,t])=>`<option value="${v}"${(p.maxp||"")===v?" selected":""}>${t}</option>`).join("")}</select><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></label>`:""}
${temTipo?`<button class="chip" aria-pressed="${p.tipo==="Restaurante"}" data-act="pf:tipo:Restaurante">Em restaurantes</button><button class="chip" aria-pressed="${p.tipo==="Bar"}" data-act="pf:tipo:Bar">Em bares</button>`:""}</div></div>
<p class="m-count" style="margin:14px 0 4px"><span>${num(n)} ${n===1?"evento":"eventos"}</span></p>
${n?`<div class="m-agenda">${vis.map(mEvRow).join("")}</div>`:`<div class="card state"><div class="big brand">${ic("star")}</div><h3>${E.length?"Nenhum evento com esses filtros":"Ainda não há eventos"}</h3><p class="sub">${E.length?"Tente outro período, cidade ou categoria.":"Os eventos aparecem aqui quando as fontes forem coletadas."}</p>${E.length?`<button class="btn soft" data-act="pfclear">Limpar filtros</button>`:""}</div>`}
${n>vis.length?`<div style="text-align:center;margin:16px 0"><button class="btn soft" data-act="pmore">Ver mais (${num(n-vis.length)})</button></div>`:""}`};
'''

PROFILE = r'''
V.profile=()=>{const L=lvl(S.xp),pct=L.next?Math.round((S.xp-L.from)/(L.next-L.from)*100):100,medals=5+Object.values(S.specs).filter(v=>v>=SPEC_MAX).length,nome=quemSou();
return`<div class="two"><div><div class="m-pf"><div class="m-pf-top"><span class="m-up">Passaporte urbano</span><button class="m-lk" data-go="favs">${ic("heart")}<span>Favoritos</span></button></div>
<div class="m-pf-id"><div class="row" style="gap:14px;min-width:0"><div class="m-av" aria-hidden="true">${esc((nome[0]||"?").toUpperCase())}</div><div style="min-width:0"><h1>${esc(nome)}</h1><p class="sub">${L.name}</p></div></div><span class="m-lvl">Nível ${L.i+1}</span></div>
<div class="m-xp"><div class="row between"><span>Progresso de exploração</span><b>${num(S.xp)}${L.next?" / "+num(L.next):""} XP</b></div><div class="m-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}" aria-label="Progresso para o próximo nível"><i style="width:${pct}%"></i></div>${S.pending?`<p class="note">${S.pending} XP pendentes de validação.</p>`:""}</div></div>
<div class="m-metrics"><div><b>${S.hist.length}</b><span>Experiências</span></div><div><b>${S.hist.filter(h=>h.rated).length}</b><span>Avaliações</span></div><div><b>${medals}</b><span>Medalhas</span></div></div>
<section class="m-sec"><div class="m-sh"><h3>Extrato de XP</h3></div><div style="border-top:1px solid var(--line)">${S.ledger.length?"":`<div class="m-xr"><span class="sub">Nenhum registro de XP ainda.</span></div>`}${S.ledger.slice(0,5).map(x=>`<div class="m-xr"><span><b>${esc(x.t)}</b><small>${x.d}</small></span><span class="m-v${x.s==="ok"?"":" pend"}">${x.s==="ok"?"+"+x.a:x.a+" pendente"}</span></div>`).join("")}</div><p class="note" style="margin-top:8px">Cada alteração de XP vira um registro. Nada é somado direto no saldo.</p></section></div>
<div class="list card">${li("list","Meu histórico","Experiências registradas","history")}${li("medal","Minhas conquistas","Medalhas e colecionáveis","badges")}${li("trophy","Especializações","Seu progresso por categoria","specs")}${li("flame","Missões","Desafios em andamento","missions")}${li("gift","Recompensas","Cupons e benefícios","rewards")}${li("people","Ranking","Veja sua posição","ranking")}${li("bell","Notificações","","notifs")}${li("gear","Configurações","Privacidade e permissões","settings")}${li("shield","Segurança","Senha, 2FA e dispositivos","security")}${li("help","Ajuda e suporte","","help")}<button class="li" data-act="logout"><span class="ico">${ic("logout")}</span><span class="grow"><b>Sair da conta</b></span></button></div></div>`};
'''

FAVS = r"""
V.favs=()=>{const t=S.tab.favs,ks=[...S.fav].filter(k=>k.startsWith(t+":"));
let body="";
if(t==="p")body=ks.map(k=>PM[k.slice(2)]).filter(Boolean).map(p=>mCard(p,"4/4.8")).join("");
if(t==="e")body=ks.map(k=>EM[k.slice(2)]).filter(Boolean).map(mEvRow).join("");
if(t==="d")body=`<div class="list card">`+ks.map(k=>{const[,pid,i]=k.split(":");const p=PM[pid];return p?dishRow(p,p.dishes[+i],+i):""}).join("")+`</div>`;
return`<div class="top"><h1>Favoritos</h1></div>${segs("favs",[["p","Locais"],["d","Pratos"],["e","Eventos"]])}<div class="${t==="p"?"m-grid":t==="e"?"m-agenda":"list"}" style="margin-top:14px">${ks.length?body:`<div class="card state" style="grid-column:1/-1"><div class="big brand">${ic("heart")}</div><h3>Nada salvo aqui ainda</h3><p class="sub">Toque no coração de um local, prato ou evento para guardar.</p><button class="btn soft" data-go="explore">Explorar</button></div>`}</div>`};
"""

CAL = '<symbol id="i-calendar" viewBox="0 0 24 24"><rect x="3" y="4.5" width="18" height="17" rx="2"/><path d="M16 2.5v4M8 2.5v4M3 10h18"/></symbol>\n'


def trocar(h, ini, fim, novo, base):
    i = h.index(ini, base)
    j = h.index(fim, i + len(ini))
    return h[:i] + novo.lstrip("\n").rstrip("\n") + "\n" + h[j:]


def main(arq):
    h = open(arq, encoding="utf-8").read()
    if MARCA in h:
        print("já aplicado")
        return
    base = h.index("const TABS")
    # 1) telas
    i_home = h.index("\nV.home=()=>{", base - 300000)
    h = h[:i_home] + "\n" + HELPERS.strip("\n") + "\n" + h[i_home:]
    base2 = h.index("const TABS") - 300000
    h = trocar(h, "\nV.home=()=>{", "\nV.foryou=", HOME, base2).replace("\nV.foryou=", "\nV.foryou=", 1)
    h = trocar(h, "\nV.explore=()=>{", "\nfunction filterSheet", EXPLORE, base2)
    h = trocar(h, "\nV.parties=()=>{", "\nV.event=", PARTIES, base2)
    h = trocar(h, "\nV.favs=()=>{", "\nV.profile=", FAVS, base2)
    h = trocar(h, "\nV.profile=()=>{", "\nV.history=", PROFILE, base2)
    # novas ações dos filtros rápidos
    ant = 'case"qtype":{const s=S.filt.types;s.has(a)?s.delete(a):s.add(a);render();break}'
    assert ant in h, "ação qtype não encontrada"
    h = h.replace(ant, ant + 'case"qcui":{const s=S.filt.cuisines;s.has(a)?s.delete(a):s.add(a);render();break}'
                  'case"qall":{S.filt.types=new Set();S.filt.cuisines=new Set();render();break}', 1)
    # 2) abas com os ícones do modelo
    ant = 'const TABS=[["home","Início","home"],["explore","Explorar","compass"],["parties","Festas","star"],'
    assert ant in h, "TABS não encontrado"
    h = h.replace(ant, 'const TABS=[["home","Início","compass"],["explore","Explorar","search"],["parties","Festas","calendar"],', 1)
    assert '<symbol id="i-home"' in h
    h = h.replace('<symbol id="i-home"', CAL + '<symbol id="i-home"', 1)
    ant = 'const pc=$("#pcity");if(pc)pc.addEventListener("change",e=>{S.pf.cidade=e.target.value;S.pn=24;render()});'
    assert ant in h, "ligação do seletor de cidade não encontrada"
    h = h.replace(ant, ant + 'const pm=$("#pmax");if(pm)pm.addEventListener("change",e=>{S.pf.maxp=e.target.value;S.pn=24;render()});', 1)
    # 3) só Inter
    h, n = re.subn(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/css2\?family=Inter[^"]*">',
                   '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400..700&display=swap">', h, count=1)
    assert n == 1, "link das fontes não encontrado"
    # 4) CSS por último
    k = h.index("</style>")
    h = h[:k] + CSS + h[k:]
    open(arq, "w", encoding="utf-8").write(h)
    print("ok")


if __name__ == "__main__":
    main(sys.argv[1])
