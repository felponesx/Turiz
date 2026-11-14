const { chromium } = require('playwright');
const S = process.env.SHOTS || '.';
(async () => {
  const b = await chromium.launch();
  let fails = 0; const ok = (c, m) => { console.log((c ? 'OK   ' : 'FALHA'), m); if (!c) fails++; };
  for (const [name, vp, mobile] of [['mobile', {width:390,height:844}, true], ['desktop', {width:1440,height:900}, false]]) {
    const ctx = await b.newContext({ viewport: vp, isMobile: mobile, hasTouch: mobile, reducedMotion:'reduce' });
    const page = await ctx.newPage(); const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    await page.goto('file://'+process.argv[2]);
    await page.evaluate(()=>go('login',null,true)); await page.fill('#f-mail','admin'); await page.fill('#f-pass','admin');
    await page.evaluate(()=>submitAuth(new Event('submit')));
    await page.waitForTimeout(600);
    for (const demo of [false, true]) {
      await page.evaluate(d=>applyDemo(d), demo);
      const k = `${name}${demo?'+demo':''}`;
      const info = await page.evaluate(()=>({reais:E.filter(e=>e.real).length, demo:E.filter(e=>e.demo).length, hoje:E.filter(e=>e.real&&e.day==='hoje').length,
        vencidos:E.filter(e=>e.real&&e.ini<Date.now()-3*36e5&&!(e.fim&&e.fim>Date.now())).length, semData:E.filter(e=>e.real&&!e.ini).length}));
      console.log(k, JSON.stringify(info));
      ok(info.reais>0, `${k}: eventos reais carregados (${info.reais})`);
      ok(info.vencidos===0, `${k}: nenhum evento vencido na lista`);
      ok(demo ? info.demo>0 : info.demo===0, `${k}: eventos de exemplo só quando ligados`);
      await page.evaluate(()=>{S.tab.parties='prox';S.pf={q:'',g:'',cidade:'',tipo:'',preco:''};S.stack=[];go('parties',null,true)}); await page.waitForTimeout(500);
      const cards = await page.locator('#app .pcard, main .pcard, .pcard').count();
      ok(cards>0, `${k}: Festas mostra cards (${cards})`);
      const imgs = await page.evaluate(()=>({img:document.querySelectorAll('.pcard img.evimg').length, tile:document.querySelectorAll('.pcard .evtile').length}));
      ok(imgs.img+imgs.tile>0, `${k}: cada card tem foto real ou bloco neutro (${JSON.stringify(imgs)})`);
      await page.waitForTimeout(800); // sem rede para as fotos: onerror troca por bloco neutro
      const quebradas = await page.evaluate(()=>[...document.querySelectorAll('.pcard img.evimg')].filter(i=>i.complete&&i.naturalWidth===0).length);
      ok(quebradas===0, `${k}: nenhuma imagem quebrada visível`);
      const overflow = await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1);
      ok(!overflow, `${k}: sem rolagem horizontal em Festas`);
      await page.screenshot({path:`${S}/shots/ev-${k}-parties.png`});
      // busca natural
      await page.fill('#pq','shows hoje em São Paulo'); await page.waitForTimeout(700);
      const nl = await page.evaluate(()=>({txt:document.querySelector('.evinterp')?.textContent||'', n:document.querySelectorAll('.pcard').length, pq:S.pf.q}));
      ok(/hoje/.test(nl.txt)&&/São Paulo/.test(nl.txt)&&/show/.test(nl.txt), `${k}: busca natural interpretada -> ${nl.txt.trim().slice(0,70)}`);
      const todosHoje = await page.evaluate(()=>{const f=evNL('shows hoje em São Paulo').f;return evFilter(E,f).every(e=>e.cidade==='São Paulo'&&(e.ini>=Date.now()-3*36e5||e.fim>Date.now()))});
      ok(todosHoje, `${k}: resultado da busca só tem eventos de hoje/futuros em São Paulo`);
      await page.screenshot({path:`${S}/shots/ev-${k}-busca.png`});
      await page.fill('#pq',''); await page.waitForTimeout(500);
      // filtros
      await page.locator('[data-act="pf:g:musica_entretenimento"]').first().click({force:true}); await page.waitForTimeout(300);
      const g = await page.evaluate(()=>document.querySelectorAll('.pcard').length); ok(g>=0, `${k}: filtro de categoria aplicado (${g})`);
      await page.locator('[data-act="pf:preco:free"]').first().click({force:true}); await page.waitForTimeout(300);
      const fr = await page.evaluate(()=>[...document.querySelectorAll('.pcard')].every(c=>/Gratuito/.test(c.textContent)));
      ok(fr, `${k}: filtro gratuito só traz gratuitos`);
      await page.evaluate(()=>{S.pf={q:'',g:'',cidade:'',tipo:'',preco:''};S.tab.parties='prox';render()}); await page.waitForTimeout(300);
      // pagina do evento real
      const eid = await page.evaluate(()=>E.find(e=>e.real&&e.ticket).id);
      await page.evaluate(id=>{S.stack=[];go('event',id,true)},eid); await page.waitForTimeout(400);
      const ev = await page.evaluate(()=>{const a=document.querySelector('.cta-bar a');return{href:a?.href||'',rel:a?.rel||'',tgt:a?.target||'',h1:document.querySelector('h1')?.textContent||'',fonte:/Fonte dos dados/.test(document.body.textContent), ex:/exemplo/i.test(document.querySelector('.sheet-card')?.textContent||'')}});
      ok(/^https:/.test(ev.href)&&/noopener/.test(ev.rel)&&ev.tgt==='_blank', `${k}: ingresso abre o site oficial (${ev.href.slice(0,40)}…)`);
      ok(ev.fonte&&!ev.ex, `${k}: página do evento mostra fonte e não se diz exemplo`);
      const of2 = await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1); ok(!of2, `${k}: página do evento sem rolagem horizontal`);
      await page.screenshot({path:`${S}/shots/ev-${k}-evento.png`});
      // home e explorar
      await page.evaluate(()=>{S.stack=[];go('home',null,true)}); await page.waitForTimeout(400); await page.screenshot({path:`${S}/shots/ev-${k}-home.png`});
      await page.evaluate(()=>{S.filt.q='shows este mês';S.stack=[];go('explore',null,true)}); await page.waitForTimeout(500);
      const ex = await page.evaluate(()=>/Eventos/.test(document.body.textContent)&&document.querySelectorAll('.hscroll .pcard').length); ok(ex>0, `${k}: Explorar mostra eventos para "shows este mês" (${ex})`);
      await page.screenshot({path:`${S}/shots/ev-${k}-explorar.png`});
      await page.evaluate(()=>{S.filt.q='';});
      // favoritos de evento real
      await page.evaluate(id=>{S.fav.add('e:'+id);S.tab.favs='e';S.stack=[];go('favs',null,true)},eid); await page.waitForTimeout(300);
      ok(await page.locator('.pcard').count()>0, `${k}: favoritos lista evento real`);
      // evento cancelado
      const canc = await page.evaluate(()=>{const e=E.find(e=>e.real);const c={...e,id:'rx',status:'cancelado',ticket:''};E.push(c);EM.rx=c;S.stack=[];go('event','rx',true);return true}); await page.waitForTimeout(300);
      ok(/Cancelado/.test(await page.locator('.sheet-card').innerText()) && await page.locator('.cta-bar button[disabled]').count()===1, `${k}: evento cancelado mostra status e bloqueia ingresso`);
      await page.evaluate(()=>{const i=E.findIndex(e=>e.id==='rx');E.splice(i,1);delete EM.rx});
    }
    ok(errors.length===0, `${name}: sem erros de JavaScript ${JSON.stringify(errors).slice(0,200)}`);
    await ctx.close();
  }
  await b.close(); console.log(fails? `${fails} FALHAS`:'TUDO OK'); process.exit(fails?1:0);
})();
