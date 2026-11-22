const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();let f=0;const ok=(c,m)=>{console.log(c?'OK   ':'FALHA',m);if(!c)f++};
const ctx=await b.newContext({viewport:{width:390,height:844},isMobile:true,reducedMotion:'reduce'});const p=await ctx.newPage();
const er=[];p.on('pageerror',e=>er.push(e.message));p.on('dialog',d=>{er.push('DIALOG '+d.message());d.dismiss()});
await p.goto('file://'+process.argv[2]);await p.evaluate(()=>go('login',null,true));await p.fill('#f-mail','admin');await p.fill('#f-pass','admin');await p.evaluate(()=>submitAuth(new Event('submit')));await p.waitForTimeout(800);
await p.evaluate(()=>{IMGP.on=true;applyDemo(true)});
const telas=[['home'],['explore'],['parties'],['favs'],['foryou'],['profile'],['notifs'],['settings']];
const ver=async(rot)=>{await p.waitForTimeout(250);const r=await p.evaluate(()=>({xss:window.__xss,inj:document.querySelectorAll('img[src="x"],svg[onload],script:not([src]):not([type])').length-document.querySelectorAll('script:not([src]):not([type])').length+0,
  js:[...document.querySelectorAll('a[href],[src]')].filter(e=>/^\s*javascript:/i.test(e.getAttribute('href')||e.getAttribute('src')||'')).length,
  on:[...document.querySelectorAll('*')].filter(e=>[...e.attributes].some(a=>/^on/i.test(a.name)&&!/^(ev|pl)ImgFail\(this\)$/.test(a.value))).length}));
  ok(!r.xss&&!r.js&&!r.on&&r.inj<=0,`${rot}: sem execução/URL javascript/handlers injetados ${JSON.stringify(r)}`)};
for(const [t] of telas){await p.evaluate(t=>{S.stack=[];go(t,null,true)},t);await ver('tela '+t)}
// lugares com payload (os 400 primeiros por nome mutado) e suas abas
const pid=await p.evaluate(()=>P.find(x=>/onerror|svg|script|javascript/.test(x.name)).id);
for(const t of ['sobre','cardapio','aval','eventos']){await p.evaluate(([t,id])=>{S.tab.place=t;S.stack=[];go('place',id,true)},[t,pid]);await ver('lugar/'+t)}
for(const id of await p.evaluate(()=>P.filter(x=>REDES[x.id]||CARD[x.id]||IMGS[x.id]).slice(0,6).map(x=>x.id))){for(const t of ['sobre','cardapio']){await p.evaluate(([t,id])=>{S.tab.place=t;S.stack=[];go('place',id,true)},[t,id]);await ver('lugar com dados externos '+t)}}
// eventos reais e mapa
for(const e of await p.evaluate(()=>E.filter(e=>e.real).slice(0,5).map(e=>e.id))){await p.evaluate(id=>{S.stack=[];go('event',id,true)},e);await ver('evento '+e);
  await p.evaluate(()=>{const b=document.querySelector('.acoes [data-act^="mapa"]');b&&b.click()});await ver('evento/mapa')}
// busca com payload digitado
await p.evaluate(()=>{S.stack=[];go('parties',null,true)});
await p.fill('#pq','<img src=x onerror=window.__xss=1>');await p.waitForTimeout(500);await ver('busca natural com payload');
await p.evaluate(()=>{S.filt.q='"><svg onload=window.__xss=1>';S.stack=[];go('explore',null,true)});await ver('explorar com payload');
// links externos têm rel seguro
const rels=await p.evaluate(()=>[...document.querySelectorAll('a[target="_blank"]')].filter(a=>!/noopener/.test(a.rel)).length);ok(rels===0,'todo link externo tem rel=noopener');
ok(er.length===0,'sem erros/diálogos: '+JSON.stringify(er).slice(0,300));
await b.close();console.log(f?f+' FALHAS':'TUDO OK');process.exit(f?1:0)})();
