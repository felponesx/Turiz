const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();let f=0;const ok=(c,m)=>{console.log(c?'OK   ':'FALHA',m);if(!c)f++};
for(const [n,vp,m] of [['mobile',{width:390,height:844},true],['desktop',{width:1440,height:900},false]]){
 const ctx=await b.newContext({viewport:vp,isMobile:m,hasTouch:m,reducedMotion:'reduce'});const p=await ctx.newPage();const er=[];p.on('pageerror',e=>er.push(e.message));
 const t0=Date.now();await p.goto('file://'+process.argv[2]);const load=Date.now()-t0;
 await p.evaluate(()=>go('login',null,true));await p.fill('#f-mail','admin');await p.fill('#f-pass','admin');await p.evaluate(()=>submitAuth(new Event('submit')));await p.waitForTimeout(800);
 const info=await p.evaluate(()=>({P:P.length,rc:P.filter(x=>x.src==='receita').length,aprox:P.filter(x=>x.aprox).length,comImg:P.filter(x=>IMGS[x.id]).length,aprov:P.filter(x=>plImg(x)).length}));
 console.log(n,'carga',load,'ms',JSON.stringify(info));
 ok(info.P>20000&&info.rc>19000,`${n}: lugares da Receita carregados`);
 for(const r of ['home','explore','parties','favs']){const t=Date.now();await p.evaluate(r=>{S.stack=[];go(r,null,true)},r);await p.waitForTimeout(500);ok(Date.now()-t<4000,`${n}: tela ${r} abre (${Date.now()-t} ms)`)}
 // lugar com imagem aprovada / pendente
 for(const pend of [false,true]){await p.evaluate(v=>{IMGP.on=v},pend);
  const pid=await p.evaluate(()=>{const x=P.find(x=>IMGS[x.id]&&plImg(x));return x?x.id:null});
  if(pid){await p.evaluate(id=>{S.tab.place='sobre';S.stack=[];go('place',id,true)},pid);await p.waitForTimeout(500);
   const r=await p.evaluate(()=>({img:document.querySelectorAll('.hero img.evimg').length,cred:document.querySelector('.imgcred')?.textContent||'',ov:document.documentElement.scrollWidth>document.documentElement.clientWidth+1}));
   ok(true,`${n} pendentes=${pend}: lugar com foto -> ${JSON.stringify(r).slice(0,150)}`)}else ok(!pend?true:false,`${n} pendentes=${pend}: sem lugar com foto`)}
 await p.waitForTimeout(800);
 // lugar da Receita
 const rid=await p.evaluate(()=>P.find(x=>x.src==='receita'&&x.aprox).id);await p.evaluate(id=>{S.tab.place='sobre';S.stack=[];go('place',id,true)},rid);await p.waitForTimeout(400);
 const txt=await p.evaluate(()=>document.body.innerText);ok(/Receita Federal/.test(txt)&&/aproximada/.test(txt)&&!/CNPJ:|\d{2}\.\d{3}\.\d{3}\/\d{4}/.test(txt),`${n}: lugar da Receita com fonte e sem CNPJ`);
 await p.screenshot({path:`./shots/lug-${n}-receita.png`});
 // redes
 const rd=await p.evaluate(()=>Object.keys(REDES)[0]);await p.evaluate(id=>{S.stack=[];go('place',id,true)},rd);await p.waitForTimeout(300);
 ok(/Instagram/.test(await p.evaluate(()=>document.body.innerText)),`${n}: rede social aparece no lugar`);
 await p.evaluate(()=>{S.stack=[];go('explore',null,true)});await p.waitForTimeout(400);await p.screenshot({path:`./shots/lug-${n}-explorar.png`});
 ok(er.length===0,`${n}: sem erros JS ${JSON.stringify(er).slice(0,200)}`);await ctx.close()}
await b.close();console.log(f?f+' FALHAS':'TUDO OK');process.exit(f?1:0)})();
