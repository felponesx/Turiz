const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();let f=0;const ok=(c,m)=>{console.log(c?'OK   ':'FALHA',m);if(!c)f++};
for(const [n,vp,m] of [['mobile',{width:390,height:844},true],['desktop',{width:1440,height:900},false]]){
const ctx=await b.newContext({viewport:vp,isMobile:m,hasTouch:m,reducedMotion:'reduce'});const p=await ctx.newPage();const er=[];p.on('pageerror',e=>er.push(e.message));
await p.goto('file://'+process.argv[2]);await p.evaluate(()=>go('login',null,true));await p.fill('#f-mail','admin');await p.fill('#f-pass','admin');await p.evaluate(()=>submitAuth(new Event('submit')));await p.waitForTimeout(800);
await p.evaluate(()=>applyDemo(true));
const c=await p.evaluate(()=>{const R=fn=>P.filter(fn).length;return{total:P.length,foto:R(x=>plFoto(x)),fotoReal:R(x=>plImg(x)),cardapio:R(x=>CARD[x.id]||(x.dishes&&x.dishes.length)),endereco:R(x=>x.addr&&x.addr.trim()),aval:R(x=>{const r=reviewsOf(x);return r&&r.length}),nota:R(x=>x.rating!=null),
 evFoto:E.filter(e=>/<img/.test(evMedia(e))).length,ev:E.length}}).catch(e=>e.message);
console.log(n,JSON.stringify(c));
if(typeof c==='object'){for(const k of ['foto','cardapio','endereco','aval','nota'])ok(c[k]===c.total,`${n}: ${k} em todos os ${c.total} lugares (${c[k]})`);ok(c.evFoto===c.ev,`${n}: foto em todos os ${c.ev} eventos (${c.evFoto})`)}
for(const r of ['home','explore','parties','favs','foryou','profile']){await p.evaluate(r=>{S.stack=[];go(r,null,true)},r);await p.waitForTimeout(400)}
const pid=await p.evaluate(()=>P.find(x=>x.src==='receita').id);
for(const t of ['sobre','cardapio','aval','eventos']){await p.evaluate(([t,id])=>{S.tab.place=t;S.stack=[];go('place',id,true)},[t,pid]);await p.waitForTimeout(350);await p.screenshot({path:`./shots/cob-${n}-${t}.png`})}
await p.evaluate(()=>{S.stack=[];go('home',null,true)});await p.waitForTimeout(500);await p.screenshot({path:`./shots/cob-${n}-home.png`,fullPage:false});
await p.evaluate(()=>{S.tab.parties='prox';S.stack=[];go('parties',null,true)});await p.waitForTimeout(500);await p.screenshot({path:`./shots/cob-${n}-festas.png`});
await p.evaluate(()=>{S.stack=[];go('explore',null,true)});await p.waitForTimeout(500);await p.screenshot({path:`./shots/cob-${n}-explorar.png`});
ok(er.length===0,`${n}: sem erros JS ${JSON.stringify(er).slice(0,200)}`);await ctx.close()}
await b.close();console.log(f?f+' FALHAS':'TUDO OK');process.exit(f?1:0)})();
