import sys
dst=sys.argv[1]; h=open(dst,encoding="utf-8").read()
if "/* ===== REBRAND MINIMALISTA ===== */" in h: print("já aplicado"); sys.exit(0)
def sub(old,new,count=1):
    global h
    assert h.count(old)==count,(old[:70],h.count(old)); h=h.replace(old,new)
CSS=r'''
/* ===== REBRAND MINIMALISTA ===== */
/* Plano, calmo, sem brilho/gradiente/vidro. O logotipo não muda. Claro é o padrão; escuro em Configurações. */
:root{--bg:#FAFAF8;--tint:transparent;--surface:#FFFFFF;--surface-2:#F4F4F1;--ink:#1A1D1C;--ink-2:#69706E;--line:#E8E8E3;
  --brand:#1E5A5C;--brand-ink:#FFFFFF;--brand-soft:#EBF1F0;--gold:#7C6A3E;--gold-soft:#F3F0E8;--grad:#1E5A5C;--dark-grad:#1E5A5C;--gold-grad:#7C6A3E;
  --glow:none;--shadow:none;--shadow-sm:none;--r:12px;--r-lg:16px;--font-display:'Figtree',system-ui,sans-serif;
  --ok:#2E6B4E;--ok-soft:#E8F1EC;--warn:#7D5F1E;--warn-soft:#F4EEDD;--bad:#9A4038;--bad-soft:#F5E6E3;--map-land:#EEF0EE;--map-block:#F7F8F7;--map-park:#DDE8E0;--map-water:#D2E0E3}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0F1415;--surface:#151B1C;--surface-2:#121819;--ink:#E8ECEB;--ink-2:#8F9A98;--line:#232B2C;
  --brand:#7FBDB4;--brand-ink:#0A1D1C;--brand-soft:#192A2A;--gold:#C2A66C;--gold-soft:#2A261A;--grad:#2C6E70;--dark-grad:#173B3D;--ok-soft:#173025;--warn-soft:#2D2616;--bad-soft:#331C19;--map-land:#162021;--map-block:#1A2627;--map-park:#1B2D25;--map-water:#16292D}}
:root[data-theme="dark"]{--bg:#0F1415;--surface:#151B1C;--surface-2:#121819;--ink:#E8ECEB;--ink-2:#8F9A98;--line:#232B2C;
  --brand:#7FBDB4;--brand-ink:#0A1D1C;--brand-soft:#192A2A;--gold:#C2A66C;--gold-soft:#2A261A;--grad:#2C6E70;--dark-grad:#173B3D;--ok-soft:#173025;--warn-soft:#2D2616;--bad-soft:#331C19;--map-land:#162021;--map-block:#1A2627;--map-park:#1B2D25;--map-water:#16292D}
h1,h2,h3,.top h1{font-family:var(--font-display);font-weight:600;letter-spacing:-.01em}
.eyebrow{letter-spacing:.06em;font-weight:600}
/* tudo plano */
.card,.pcard,.hrow,.feat,.search,.iconbtn,.btn,.chip,.tabs,.rbadge,.cta-pill{box-shadow:none!important}
.pcard,.hrow,.feat,.card{border:1px solid var(--line);border-radius:var(--r-lg)}
.hrow{border-radius:var(--r-lg);padding:10px}.hrow .ph{border-radius:10px}
.search{border-radius:12px;min-height:48px}
.btn{border-radius:10px;min-height:46px}
.btn.soft{background:var(--brand-soft);color:var(--brand)}
.chip,.tabs{border-radius:10px}.tabs button{border-radius:8px}
.chip[aria-pressed="true"],.tabs button[aria-selected="true"]{background:var(--brand);color:var(--brand-ink);box-shadow:none}
.cat .c,.ico{background:var(--brand-soft);color:var(--brand);box-shadow:none;border-radius:14px}
.cat .c{width:52px;height:52px}
.ind{background:var(--brand-soft)!important;box-shadow:none!important}
.tabbar button[aria-current="page"]{background:none;color:var(--brand);box-shadow:none}
.tabbar{left:0;right:0;transform:none;bottom:0;width:auto;border-radius:0;border:0;border-top:1px solid var(--line);padding:6px 8px calc(6px + env(safe-area-inset-bottom,0px));background:var(--surface)!important;-webkit-backdrop-filter:none!important;backdrop-filter:none!important}
.hero .iconbtn{background:var(--surface);color:var(--ink);border:1px solid var(--line);-webkit-backdrop-filter:none;backdrop-filter:none}
.hero .iconbtn[aria-pressed="true"]{background:var(--brand);color:var(--brand-ink)}
.heart{background:var(--surface);color:var(--ink);border:1px solid var(--line);-webkit-backdrop-filter:none;backdrop-filter:none}
.sheet-card{border-radius:18px 18px 0 0;margin-top:-18px}
.cta-bar{bottom:calc(66px + env(safe-area-inset-bottom,0px))}
.rbadge{background:var(--surface);border:1px solid var(--line)}
.dchip{display:none}
.switch[aria-checked="true"]{background:var(--brand)}
/* destaque vira cartão comum: imagem em cima, texto embaixo */
.feat .in{position:static;color:var(--ink);padding:14px 16px}
.feat .meta{color:var(--ink-2)}.feat h3{font-size:1.1rem}
.cta-pill{background:var(--brand-soft);color:var(--brand);border-radius:10px;font-weight:600}
.pcard-b{padding:12px 14px 14px;gap:4px}.pcard h3{font-size:1rem}
.kpis{display:none}
.kpi-line{color:var(--ink-2);font-size:.86rem;margin:2px 0 14px}
.proto{border:0;padding:0;background:none;font-size:.7rem}
/* quando não há foto real: bloco liso, só a categoria */
.tile{width:100%;height:100%;min-height:100px;display:grid;place-content:center;justify-items:center;gap:6px;background:var(--surface-2);color:var(--ink-2);font-size:.8rem;font-weight:500;text-align:center;padding:10px}
.tile .i{width:26px;height:26px;color:var(--brand);opacity:.8}
.hero .tile .i{width:40px;height:40px}
.evtile{background:var(--surface-2);color:var(--ink-2);font-weight:500}
.imgcred{background:rgba(0,0,0,.55)}
.ph{background:var(--surface-2)}.ph::after{display:none}
@media (min-width:900px){.tabbar{display:none}}
'''
i=h.rindex("</style>"); h=h[:i]+CSS+h[i:]
# claro por padrão (escuro só se a pessoa escolher em Configurações)
sub('try{const sv=localStorage.getItem(THEME_KEY);if(sv==="light"||sv==="dark")applyTheme(sv)}catch(e){}',
    'try{const sv=localStorage.getItem(THEME_KEY);applyTheme(sv==="dark"?"dark":"light")}catch(e){applyTheme("light")}')
sub('function currentTheme(){return document.documentElement.getAttribute("data-theme")||(matchMedia("(prefers-color-scheme:dark)").matches?"dark":"light")}','function currentTheme(){return document.documentElement.getAttribute("data-theme")||"light"}')
JS=r'''
/* sem foto real: bloco liso com o tipo do local (nada de ilustração passando por foto) */
const TILE_I={bar:"glass",house:"fork",food:"fork",stage:"star",city:"pin",rooftop:"glass"};
function scene(kind,key="x",hue=20){const p=PM&&PM[key];const lab=p?(p.cuisine&&p.type==="Restaurante"?p.cuisine:p.type):(kind==="bar"?"Bar":kind==="stage"?"Evento":"Restaurante");
  return`<div class="tile"><svg class="i" aria-hidden="true"><use href="#i-${TILE_I[kind]||"fork"}"/></svg><span>${esc(lab)}</span></div>`}
'''
sub('/* ===== IMAGENS DOS LUGARES ===== */', JS+'/* ===== IMAGENS DOS LUGARES ===== */')
# placeCard: distância no texto
sub('<span class="dchip">${p.dist.toFixed(1).replace(".",",")} km</span></div>\n  <div class="pcard-b"><h3>${esc(p.name)}</h3><p class="meta"><span>${tc(p)}</span>${p.region?`<span>${esc(p.region)}</span>`:""}</p>',
    '</div>\n  <div class="pcard-b"><h3>${esc(p.name)}</h3><p class="meta"><span>${tc(p)}</span>${p.region?`<span>${esc(p.region)}</span>`:""}<span>${p.dist.toFixed(1).replace(".",",")} km</span></p>')
# Home enxuta
sub('const feat=P.filter(p=>p.type==="Restaurante"&&p.cuisine&&p.hours!=="Horário não informado").slice(0,40).sort((a,b)=>(b.rating||0)-(a.rating||0))[0]||P[0]',
    'const feat=P.find(p=>plImg(p)&&p.dist<30)||P.filter(p=>p.type==="Restaurante"&&p.cuisine&&p.hours!=="Horário não informado").slice(0,40).sort((a,b)=>(b.rating||0)-(a.rating||0))[0]||P[0]')
sub('disc=P.filter(p=>!vis.has(p.id)&&p.id!==feat.id).slice(0,6)','disc=[...P.filter(p=>plImg(p)&&p.dist<60&&p.id!==feat.id).slice(0,3),...P.filter(p=>!vis.has(p.id)&&p.id!==feat.id&&!plImg(p)).slice(0,4)]')
sub('["Eventos","ticket","go:parties:fds"],["Pizzarias","fork","explore:cuisine:Pizzaria"]];','["Eventos","ticket","go:parties:fds"],["Pizzarias","fork","explore:cuisine:Pizzaria"]];')
sub('<div class="ph">${scene(feat.scene,feat.id,feat.hue)}${heart(favKey("p",feat.id))}</div>','<div class="ph">${plMedia(feat)}${heart(favKey("p",feat.id))}</div>')
sub('<p class="sub">Qual será o seu próximo destino?</p><span class="proto" style="margin-top:8px">Protótipo · dados de exemplo</span></div>','<p class="sub">Qual será o seu próximo destino?</p></div>')
sub('<div class="card kpis" aria-label="Resumo da base"><div><b>${num(KPI.all)}</b><span>lugares mapeados</span></div><div><b>${num(KPI.rest)}</b><span>restaurantes</span></div><div><b>${num(KPI.bar)}</b><span>bares</span></div></div>',
    '<p class="kpi-line">${num(KPI.all)} lugares · ${num(KPI.rest)} restaurantes · ${num(KPI.bar)} bares${DEMO.on?" · <span class=\\"exm\\">exemplo</span> notas e preços":""}</p>')
open(dst,"w",encoding="utf-8").write(h); print("ok")
