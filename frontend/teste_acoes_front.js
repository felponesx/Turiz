const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();let f=0;const ok=(c,m)=>{console.log(c?'OK   ':'FALHA',m);if(!c)f++};
for(const [n,vp,m] of [['mobile',{width:390,height:844},true],['desktop',{width:1440,height:900},false]]){
const ctx=await b.newContext({viewport:vp,isMobile:m,hasTouch:m,reducedMotion:'reduce'});const p=await ctx.newPage();const er=[];p.on('pageerror',e=>er.push(e.message));
await p.goto('file://'+process.argv[2]);await p.evaluate(()=>go('login',null,true));await p.fill('#f-mail','admin');await p.fill('#f-pass','admin');await p.evaluate(()=>submitAuth(new Event('submit')));await p.waitForTimeout(700);
const eid=await p.evaluate(()=>E.find(e=>e.real&&e.loc.lat!=null&&!e.placeId).id);
await p.evaluate(id=>{S.stack=[];go('event',id,true)},eid);await p.waitForTimeout(400);
const h=await p.evaluate(()=>[...document.querySelectorAll('.acoes .btn')].map(b=>Math.round(b.getBoundingClientRect().height)+'x'+Math.round(b.getBoundingClientRect().width)+' '+b.scrollWidth+'/'+b.clientWidth));
console.log(n,'evento botões',JSON.stringify(h));
ok(new Set(h.map(x=>x.split(' ')[0])).size===1,`${n}: três botões com mesma altura e largura`);
ok(h.every(x=>{const [a,b2]=x.split(' ')[1].split('/');return +a<=+b2}),`${n}: texto cabe nos botões`);
await p.evaluate(()=>document.querySelectorAll('.acoes .btn')[2].click());await p.waitForTimeout(500);
const ms=await p.evaluate(()=>[...document.querySelectorAll('#panel a.li')].map(a=>a.href.slice(0,30)));
ok(ms.length===4&&!ms.some(x=>/openstreetmap/.test(x)),`${n}: Mapa abre escolha de apps (${ms.join(' | ')})`);
await p.screenshot({path:`./shots/acoes-${n}-evento.png`});
await p.evaluate(()=>{S.stack=[];go('event',null,true)}).catch(()=>{});
const pid=await p.evaluate(()=>P.find(x=>x.lat!=null).id);
await p.evaluate(()=>{closeSheet&&closeSheet()});
await p.evaluate(id=>{S.tab.place='sobre';S.stack=[];go('place',id,true)},pid);await p.waitForTimeout(400);
const hp=await p.evaluate(()=>[...document.querySelectorAll('.acoes .btn')].map(b=>Math.round(b.getBoundingClientRect().height)+'x'+Math.round(b.getBoundingClientRect().width)));
ok(hp.length===3&&new Set(hp).size===1,`${n}: lugar com três botões iguais (${hp.join(',')})`);
await p.screenshot({path:`./shots/acoes-${n}-lugar.png`});
await p.evaluate(()=>{S.stack=[];go('explore',null,true)});await p.waitForTimeout(300);
ok(er.length===0,`${n}: sem erros JS ${JSON.stringify(er).slice(0,160)}`);await ctx.close()}
await b.close();console.log(f?f+' FALHAS':'TUDO OK');process.exit(f?1:0)})();
