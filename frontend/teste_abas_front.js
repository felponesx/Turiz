const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();let f=0;const ok=(c,m)=>{console.log(c?'OK   ':'FALHA',m);if(!c)f++};
for(const [n,vp,m] of [['mobile',{width:390,height:844},true],['desktop',{width:1440,height:900},false]]){
const ctx=await b.newContext({viewport:vp,isMobile:m,hasTouch:m,reducedMotion:'no-preference'});const p=await ctx.newPage();const er=[];p.on('pageerror',e=>er.push(e.message));
await p.goto('file://'+process.argv[2]);await p.evaluate(()=>go('login',null,true));await p.fill('#f-mail','admin');await p.fill('#f-pass','admin');await p.evaluate(()=>submitAuth(new Event('submit')));await p.waitForTimeout(700);
const pid=await p.evaluate(()=>P.find(x=>x.src==='receita').id);
await p.evaluate(id=>{S.tab.place='sobre';S.stack=[];go('place',id,true)},pid);await p.waitForTimeout(400);
const pos=()=>p.evaluate(()=>{const el=document.querySelector('.tabs.seg[data-seg="place"]');const ind=el.querySelector('.ind');const cur=el.querySelector('[aria-selected="true"]');return{ind:Math.round(ind.getBoundingClientRect().left),cur:Math.round(cur.getBoundingClientRect().left),w:Math.round(ind.getBoundingClientRect().width),cw:Math.round(cur.getBoundingClientRect().width),label:cur.textContent}});
let a=await pos();ok(Math.abs(a.ind-a.cur)<2&&Math.abs(a.w-a.cw)<2,`${n}: destaque cobre a aba "${a.label}"`);
for(const t of ['cardapio','aval','eventos']){
  await p.evaluate(t=>document.querySelector(`.tabs.seg[data-seg="place"] [data-act="tab:place:${t}"]`).click(),t);
  await p.waitForTimeout(90); const mid=await pos();   // durante a animação
  await p.waitForTimeout(700); const end=await pos();
  ok(Math.abs(end.ind-end.cur)<2&&Math.abs(end.w-end.cw)<2,`${n}: destaque chega em "${end.label}"`);
  ok(mid.ind!==end.ind||mid.cur===end.cur,`${n}: destaque se move até "${end.label}" (meio: ${mid.ind}px → ${end.ind}px)`);
  a=end;}

ok(er.length===0,`${n}: sem erros JS ${JSON.stringify(er).slice(0,160)}`);
await p.screenshot({path:`./shots/seg-${n}.png`});await ctx.close()}
await b.close();console.log(f?f+' FALHAS':'TUDO OK');process.exit(f?1:0)})();
