// Splash: marcação, acessibilidade (axe, claro e escuro), movimento reduzido, botão Entrar, avanço automático, sem erros de JS.
const { chromium } = require('playwright');
const fs = require('fs');
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
(async () => {
  const b = await chromium.launch(); let f = 0;
  const ok = (c, m) => { console.log(c ? 'OK   ' : 'FALHA', m); if (!c) f++; };
  for (const tema of ['dark', 'light']) {
    for (const [nome, vp, mob] of [['celular', { width: 390, height: 844 }, true], ['desktop', { width: 1280, height: 800 }, false], ['paisagem', { width: 844, height: 390 }, true]]) {
      const ctx = await b.newContext({ viewport: vp, isMobile: mob, reducedMotion: 'reduce' }); const p = await ctx.newPage(); const er = [];
      p.on('pageerror', e => er.push(e.message));
      await p.addInitScript(t => { try { localStorage.setItem('turiz-theme', t) } catch (e) { } }, tema);
      await p.goto('file://' + process.argv[2]); await p.waitForTimeout(300);
      const r = await p.evaluate(() => {
        const s = document.querySelector('.splash'); if (!s) return null;
        const vis = e => { if (!e) return false; const c = getComputedStyle(e), bb = e.getBoundingClientRect(); return c.visibility !== 'hidden' && +c.opacity > .99 && bb.width > 0 && bb.bottom <= innerHeight + 1 && bb.top >= -1 };
        return { rota: S.route.n, h1: s.querySelector('h1')?.textContent, logo: vis(s.querySelector('.logo-mark')), titulo: vis(s.querySelector('.sp-word')), frase: vis(s.querySelector('.sp-tag')), entrar: vis(s.querySelector('.sp-skip')),
          fundo: getComputedStyle(s).backgroundColor, rolagemH: document.documentElement.scrollWidth > innerWidth + 1 };
      });
      ok(r && r.rota === 'splash', `${tema}/${nome}: abre na splash`);
      ok(r && r.h1 === 'TURIZ', `${tema}/${nome}: título TURIZ (h1)`);
      ok(r && r.logo && r.titulo && r.frase && r.entrar, `${tema}/${nome}: logo, título, frase e botão visíveis e dentro da tela com movimento reduzido ${JSON.stringify(r && { l: r.logo, t: r.titulo, f: r.frase, e: r.entrar })}`);
      ok(r && r.fundo === 'rgb(17, 19, 18)', `${tema}/${nome}: fundo carvão em qualquer tema (${r && r.fundo})`);
      ok(r && !r.rolagemH, `${tema}/${nome}: sem rolagem horizontal`);
      await p.addScriptTag({ content: AXE });
      const ax = await p.evaluate(async () => await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } }));
      ok(ax.violations.length === 0, `${tema}/${nome}: axe sem violações ${ax.violations.map(v => v.id + ':' + v.nodes.length)}`);
      // avanço automático (movimento reduzido = mais rápido)
      await p.waitForTimeout(1300);
      ok(await p.evaluate(() => S.route.n) === 'login', `${tema}/${nome}: segue sozinho para o login (movimento reduzido ~1,2 s)`);
      ok(er.length === 0, `${tema}/${nome}: sem erros JS ${JSON.stringify(er)}`);
      await ctx.close();
    }
  }
  // teclado: Tab chega ao "Entrar", Enter vai ao login; com animação normal ainda segue em ~2,4 s
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true }); const p = await ctx.newPage();
  await p.goto('file://' + process.argv[2]); await p.waitForTimeout(250);
  await p.keyboard.press('Tab');
  ok(await p.evaluate(() => document.activeElement?.className === 'sp-skip'), 'teclado: Tab foca o botão Entrar');
  await p.keyboard.press('Enter'); await p.waitForTimeout(300);
  ok(await p.evaluate(() => S.route.n) === 'login', 'teclado: Enter no botão leva ao login');
  const p2 = await ctx.newPage(); await p2.goto('file://' + process.argv[2]);
  await p2.waitForTimeout(1800); ok(await p2.evaluate(() => S.route.n) === 'splash', 'animação normal: ainda na splash aos 1,8 s');
  await p2.waitForTimeout(900); ok(await p2.evaluate(() => S.route.n) === 'login', 'animação normal: segue ao login em ~2,4 s');
  await b.close(); console.log(f ? f + ' FALHAS' : 'TUDO OK'); process.exit(f ? 1 : 0);
})();
