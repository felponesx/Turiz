const { chromium } = require('playwright');
const fs = require('fs');
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
(async()=>{const b=await chromium.launch();const resumo={};const det={};
for(const tema of ['light','dark']){
 for(const [n,vp,m] of [['mobile',{width:390,height:844},true],['desktop',{width:1440,height:900},false]]){
  const ctx=await b.newContext({viewport:vp,isMobile:m,reducedMotion:'reduce'});const p=await ctx.newPage();
  await p.goto('file://'+process.argv[2]);await p.evaluate(()=>go('login',null,true));await p.fill('#f-mail','admin');await p.fill('#f-pass','admin');await p.evaluate(()=>submitAuth(new Event('submit')));await p.waitForTimeout(700);
  await p.evaluate(t=>applyTheme(t),tema);
  const pid=await p.evaluate(()=>P.find(x=>plImg(x)&&CARD[x.id]).id), eid=await p.evaluate(()=>E.find(e=>e.real).id);
  const telas=[['home'],['explore'],['parties'],['favs'],['profile'],['settings'],['notifs'],['place',pid,'sobre'],['place',pid,'cardapio'],['place',pid,'aval'],['place',pid,'eventos'],['event',eid],['login']];
  for(const [t,id,aba] of telas){
   await p.evaluate(([t,id,aba])=>{if(aba)S.tab.place=aba;S.stack=[];go(t,id||null,true)},[t,id,aba]);await p.waitForTimeout(350);
   await p.addScriptTag({content:AXE}).catch(()=>{});
   const r=await p.evaluate(async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']},resultTypes:['violations']}));
   for(const v of r.violations){const k=`${v.id} [${v.impact}]`;const chave=`${tema}/${n}`;(resumo[k]=resumo[k]||{});resumo[k][chave]=(resumo[k][chave]||0)+v.nodes.length;(det[k]=det[k]||{desc:v.help,exemplos:new Set()});if(det[k].exemplos.size<3)det[k].exemplos.add(`${t}${aba?'/'+aba:''}: `+v.nodes[0].html.slice(0,110).replace(/\s+/g,' ')+' || '+(v.nodes[0].any[0]?.message||v.nodes[0].failureSummary||'').slice(0,140))}
  }
  await ctx.close()}}
for(const k of Object.keys(resumo))console.log(k,'-',det[k].desc,JSON.stringify(resumo[k]),'\n   ',[...det[k].exemplos].join('\n    '));
console.log(Object.keys(resumo).length?'VIOLAÇÕES: '+Object.keys(resumo).length+' regras':'SEM VIOLAÇÕES');
await b.close()})();
