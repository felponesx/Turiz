// Festas (celular): abas de período dentro da tela; categorias em uma linha; "Pagos" e "Até R$ x" filtram certo; sem erros de JS.
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); let f = 0;
  const ok = (c, m) => { console.log(c ? 'OK   ' : 'FALHA', m); if (!c) f++; };
  for (const w of [360, 390, 412]) {
    const ctx = await b.newContext({ viewport: { width: w, height: 800 }, isMobile: true, reducedMotion: 'reduce' });
    const p = await ctx.newPage(); const er = [];
    p.on('pageerror', e => er.push(e.message));
    await p.addInitScript(() => { try { localStorage.setItem('turiz-theme', 'dark') } catch (e) { } });
    await p.goto('file://' + process.argv[2]); await p.evaluate(() => go('login', null, true));
    await p.fill('#f-mail', 'admin'); await p.fill('#f-pass', 'admin');
    await p.evaluate(() => submitAuth(new Event('submit'))); await p.waitForTimeout(600);
    await p.evaluate(() => { S.stack = []; S.tab.parties = 'prox'; S.pf = { q: '', g: '', cidade: '', tipo: '', preco: '', maxp: '' }; go('parties', null, true) });
    await p.waitForTimeout(400);
    const geo = await p.evaluate(() => {
      const seg = document.querySelector('.tabs.seg').getBoundingClientRect();
      const btns = [...document.querySelectorAll('.tabs.seg>button')].map(b => b.scrollWidth <= b.clientWidth + 1);
      const chips = [...document.querySelectorAll('.m-cats .chip')];
      const tops = new Set(chips.map(c => Math.round(c.getBoundingClientRect().top)));
      const cortados = chips.filter(c => c.scrollWidth > c.clientWidth + 1).map(c => c.textContent.trim());
      return { segDentro: seg.left >= 15 && seg.right <= innerWidth - 15, abasSemCorte: btns.every(Boolean), nAbas: btns.length,
        nChips: chips.length, linhas: tops.size, cortados, larguraTela: innerWidth };
    });
    ok(geo.segDentro, `${w}px: abas de período dentro da tela com margem de 16px`);
    ok(geo.abasSemCorte && geo.nAbas === 4, `${w}px: 4 abas de período sem texto cortado`);
    ok(geo.nChips === 4 && geo.linhas === 1, `${w}px: 4 categorias em UMA linha (${geo.nChips} chips, ${geo.linhas} linha)`);
    ok(geo.cortados.length === 0, `${w}px: nenhum rótulo de categoria cortado ${JSON.stringify(geo.cortados)}`);
    ok(await p.evaluate(() => !document.querySelector('[data-act="pf:preco:100"]') && !/Até R\$ 100/.test(document.querySelector('.evfilters')?.textContent || '')) , `${w}px: botão "Até R$ 100" saiu da linha de preço`);
    ok(await p.evaluate(() => !!document.querySelector('[data-act="pf:preco:pago"]')) && !(await p.$('#pmax')), `${w}px: "Pagos" aparece e o seletor "Até R$ x" está escondido antes de clicar`);

    const count = () => p.evaluate(() => parseInt(document.querySelector('.m-count span').textContent.replace(/\./g, ''), 10));
    const total = await count();
    ok(total === await p.evaluate(() => E.length), `${w}px: sem filtro de preço mostra todos os eventos (${total})`);

    await p.click('[data-act="pf:preco:pago"]'); await p.waitForTimeout(250);
    const pagos = await p.evaluate(() => E.filter(e => !e.free && e.price != null).length);
    ok(await count() === pagos, `${w}px: "Pagos" mostra só eventos com preço conhecido e não gratuitos (${pagos})`);
    ok(await p.$('#pmax') !== null, `${w}px: ao clicar em Pagos, aparece o seletor "Até R$ x" ao lado`);
    const opts = await p.evaluate(() => [...document.querySelectorAll('#pmax option')].map(o => o.textContent));
    ok(opts.join('|') === 'Sem limite|Até R$ 50|Até R$ 100|Até R$ 200|Até R$ 500', `${w}px: opções do teto ${opts.join(', ')}`);

    for (const v of ['50', '100', '200']) {
      await p.selectOption('#pmax', v); await p.waitForTimeout(250);
      const esp = await p.evaluate(v => E.filter(e => !e.free && e.price != null && e.price <= +v).length, v);
      ok(await count() === esp, `${w}px: Pagos + Até R$ ${v} mostra ${esp} eventos`);
    }
    await p.selectOption('#pmax', ''); await p.waitForTimeout(250);
    ok(await count() === pagos, `${w}px: "Sem limite" volta a mostrar todos os pagos (${pagos})`);

    await p.click('[data-act="pf:preco:pago"]'); await p.waitForTimeout(250);
    ok(await count() === total, `${w}px: desligar Pagos volta ao total (${total})`);
    ok(await p.$('#pmax') === null, `${w}px: seletor some quando Pagos está desligado`);

    await p.click('[data-act="pf:g:musica_entretenimento"]'); await p.waitForTimeout(250);
    ok(await p.evaluate(() => S.pf.g === 'musica_entretenimento' && document.querySelector('.m-cats [aria-pressed="true"]').textContent.trim() === 'Música'), `${w}px: categoria "Música" marca só ela`);
    ok(er.length === 0, `${w}px: sem erros de JavaScript ${JSON.stringify(er)}`);
    await ctx.close();
  }
  await b.close(); console.log(f ? f + ' FALHAS' : 'TUDO OK'); process.exit(f ? 1 : 0);
})();
