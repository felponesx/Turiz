const { chromium } = require('playwright');
const fs=require('fs');const AXE=fs.readFileSync(require.resolve('axe-core/axe.min.js'),'utf8');
(async()=>{const b=await chromium.launch();let f=0;const ok=(c,m)=>{console.log(c?'OK   ':'FALHA',m);if(!c)f++};
const ctx=await b.newContext({viewport:{width:390,height:844},isMobile:true,reducedMotion:'reduce'});const p=await ctx.newPage();const er=[];p.on('pageerror',e=>er.push(e.message));
await p.goto('file://'+process.argv[2]);await p.evaluate(()=>go('login',null,true));
ok(/Termos/.test(await p.evaluate(()=>document.body.innerText))&&/Política de Privacidade/.test(await p.evaluate(()=>document.body.innerText)),'login mostra links de Termos e Privacidade');
await p.fill('#f-mail','admin');await p.fill('#f-pass','admin');await p.evaluate(()=>submitAuth(new Event('submit')));await p.waitForTimeout(700);
await p.evaluate(()=>{S.stack=[];go('settings',null,true)});await p.waitForTimeout(300);
await p.evaluate(()=>[...document.querySelectorAll('button.li')].find(b=>/Política de privacidade/.test(b.innerText)).click());await p.waitForTimeout(400);
ok(await p.evaluate(()=>S.route.n==='legal'),'Configurações abre a Política de privacidade');
for(const [k,t] of [['priv','Quem somos'],['termos','O que é o TURIZ'],['local','cookies de publicidade'],['reemb','não vende ingressos'],['img','remover'],['emp','Razão social']]){
  await p.evaluate(k=>{S.tab.legal=k;render()},k);await p.waitForTimeout(150);
  const txt=await p.evaluate(()=>document.querySelector('.legal').innerText);ok(new RegExp(t,'i').test(txt),`aba ${k} renderiza ("${t}")`);}
await p.addScriptTag({content:AXE});const r=await p.evaluate(async()=>await axe.run(document,{runOnly:['wcag2a','wcag2aa','wcag21aa']}));ok(r.violations.length===0,'legal sem violações axe '+r.violations.map(v=>v.id));
// PROTO: nenhuma menção ao CNPJ de estabelecimentos
ok(!/\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}/.test(await p.evaluate(()=>document.body.innerText)),'sem CNPJ formatado na tela');
// exportar (protótipo) gera arquivo local
await p.evaluate(()=>{S.stack=[];go('settings',null,true)});await p.waitForTimeout(200);
await p.evaluate(()=>exportarDados());await p.waitForTimeout(300);const js=await p.evaluate(()=>{const t=document.querySelector('#panel textarea');try{return t?JSON.parse(t.value):null}catch(e){return null}});ok(js&&js.aviso&&Array.isArray(js.favoritos),'exportar (protótipo) mostra os dados em JSON para copiar (o visualizador bloqueia downloads)');
ok(er.length===0,'sem erros JS '+JSON.stringify(er));await b.close();console.log(f?f+' FALHAS':'TUDO OK');process.exit(f?1:0)})();
