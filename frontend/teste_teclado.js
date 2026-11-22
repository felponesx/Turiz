const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();let f=0;const ok=(c,m)=>{console.log(c?'OK   ':'FALHA',m);if(!c)f++};
const ctx=await b.newContext({viewport:{width:1280,height:800},reducedMotion:'reduce'});const p=await ctx.newPage();
await p.goto('file://'+process.argv[2]);await p.evaluate(()=>go('login',null,true));await p.fill('#f-mail','admin');await p.fill('#f-pass','admin');await p.evaluate(()=>submitAuth(new Event('submit')));await p.waitForTimeout(700);
await p.evaluate(()=>{S.stack=[];go('explore',null,true)});await p.waitForTimeout(400);
// 1) foco visível
const foco=async()=>p.evaluate(()=>{const e=document.activeElement;if(!e||e===document.body)return null;const c=getComputedStyle(e);const w=e.closest('.search');return{tag:e.tagName,txt:(e.getAttribute('aria-label')||e.innerText||'').slice(0,30),outline:c.outlineStyle!=='none'&&parseFloat(c.outlineWidth)>0,sombra:c.boxShadow!=='none'||(!!w&&getComputedStyle(w).boxShadow!=='none')}});
let tabs=[],semFoco=0;for(let i=0;i<14;i++){await p.keyboard.press('Tab');const x=await foco();tabs.push(x&&x.txt);if(x&&!(x.outline||x.sombra)){semFoco++;console.log('  sem indicador:',x.tag,x.txt)}}
ok(tabs.filter(Boolean).length>=10,'Tab percorre controles ('+tabs.filter(Boolean).slice(0,6).join(' | ')+')');
ok(semFoco===0,`todo elemento focado tem indicador visível (${semFoco} sem)`);
// 2) Enter ativa cartão (role=link)
await p.evaluate(()=>{document.querySelector('.m-tcard[role="link"],.m-row[role="link"],.hrow[role="link"]').focus()});await p.keyboard.press('Enter');await p.waitForTimeout(500);
ok(await p.evaluate(()=>S.route.n==='place'),'Enter abre o lugar pelo teclado');
// 3) sheet: foco entra, Tab não escapa, Esc fecha e o foco volta
await p.evaluate(()=>{S.stack=[];go('explore',null,true)});await p.waitForTimeout(300);
await p.evaluate(()=>{const b=document.querySelector('[data-act="filters"]');b.focus();b.click()});await p.waitForTimeout(500);
const dentro=async()=>p.evaluate(()=>!!document.activeElement.closest('#panel'));
ok(await dentro(),'ao abrir a folha, o foco vai para dentro dela');
let escapou=false;for(let i=0;i<25;i++){await p.keyboard.press('Tab');if(!(await dentro()))escapou=true}
ok(!escapou,'Tab não sai da folha aberta (armadilha de foco)');
await p.keyboard.press('Escape');await p.waitForTimeout(500);
ok(await p.evaluate(()=>!document.querySelector('#sheet').classList.contains('open')),'Esc fecha a folha');
ok(await p.evaluate(()=>document.activeElement&&document.activeElement.matches('[data-act="filters"]')),'o foco volta ao botão que abriu a folha');
await b.close();console.log(f?f+' FALHAS':'TUDO OK');process.exit(f?1:0)})();
