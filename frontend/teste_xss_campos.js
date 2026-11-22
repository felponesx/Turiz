const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();const p=await (await b.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'})).newPage();
const er=[];p.on('pageerror',e=>er.push(e.message));p.on('dialog',d=>d.dismiss());
await p.goto('file://'+process.argv[2]);await p.evaluate(()=>go('login',null,true));await p.fill('#f-mail','admin');await p.fill('#f-pass','admin');await p.evaluate(()=>submitAuth(new Event('submit')));await p.waitForTimeout(800);
await p.evaluate(()=>{IMGP.on=true;applyDemo(true)});
const vazou={};const coleta=async(rot)=>{await p.waitForTimeout(200);const r=await p.evaluate(()=>({f:[...new Set([...document.querySelectorAll('[data-f]')].map(e=>e.dataset.f))],xss:window.__xss,js:[...document.querySelectorAll('a[href],[src]')].filter(e=>/^\s*javascript:/i.test(e.getAttribute('href')||e.getAttribute('src')||'')).map(e=>e.tagName)}));
  for(const f of r.f)(vazou[f]=vazou[f]||new Set()).add(rot);if(r.js.length)(vazou['URL javascript:']=vazou['URL javascript:']||new Set()).add(rot+' '+r.js.join(','));if(r.xss)(vazou['EXECUTOU']=vazou['EXECUTOU']||new Set()).add(rot)};
for(const t of ['home','explore','parties','favs','foryou','profile','notifs','settings','history','ranking','map']){await p.evaluate(t=>{try{S.stack=[];go(t,null,true)}catch(e){}},t);await coleta(t)}
const ids=await p.evaluate(()=>({pl:P.filter(x=>x.type==='Restaurante'&&REDES[x.id]&&CARD[x.id]).slice(0,2).concat(P.slice(0,3)).map(x=>x.id),ev:E.filter(e=>e.real).slice(0,4).map(e=>e.id),demo:E.filter(e=>e.demo).slice(0,2).map(e=>e.id)}));
for(const id of ids.pl)for(const t of ['sobre','cardapio','aval','eventos']){await p.evaluate(([t,id])=>{S.tab.place=t;S.stack=[];go('place',id,true)},[t,id]);await coleta('lugar/'+t);
  await p.evaluate(()=>{const b=document.querySelector('[data-act^="mapa"]');b&&b.click()});await coleta('lugar/'+t+'+mapa');await p.evaluate(()=>closeSheet())}
for(const id of [...ids.ev,...ids.demo]){await p.evaluate(id=>{S.stack=[];go('event',id,true)},id);await coleta('evento '+id);await p.evaluate(id=>{S.stack=[];go('directions',id,true)},id);await coleta('rota '+id)}
for(const id of ids.pl.slice(0,2)){await p.evaluate(id=>{S.stack=[];go('directions',id,true)},id);await coleta('rota lugar')}
await p.evaluate(()=>{S.fav=new Set([...P.slice(0,3).map(p=>'p:'+p.id),...E.slice(0,3).map(e=>'e:'+e.id)]);S.tab.favs='p';S.stack=[];go('favs',null,true)});await coleta('favoritos lugares');
await p.evaluate(()=>{S.tab.favs='e';render()});await coleta('favoritos eventos');
await p.evaluate(()=>{S.tab.parties='prox';S.pf.q='show';S.stack=[];go('parties',null,true)});await coleta('festas');
await p.evaluate(()=>{S.filt.q='x';S.stack=[];go('explore',null,true)});await coleta('explorar busca');
await p.evaluate(()=>{sheet(filterSheet())});await coleta('sheet filtros');
const hist=await p.evaluate(()=>{S.stack=[];go('history',null,true);return 1});await coleta('historico');
console.log(JSON.stringify(Object.fromEntries(Object.entries(vazou).map(([k,v])=>[k,[...v].slice(0,6)])),null,1));console.log('erros',er.slice(0,3));await b.close()})();
