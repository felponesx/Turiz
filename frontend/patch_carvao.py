#!/usr/bin/env python3
"""Identidade visual "Carvão e Areia" (paleta e tipografia do modelo enviado pelo dono do projeto).

Muda SÓ a aparência do protótipo: cores, fontes (Inter + Plus Jakarta Sans), superfícies, barra de abas, painel, aviso, estados.
Não muda dados, textos, telas nem comportamento. O escuro vira o padrão; o claro continua nas Configurações.
Idempotente (marcador). Uso: python3 patch_carvao.py turiz.html"""
import re
import sys

MARCA = "/* ===== TURIZ CARVAO E AREIA ===== */"

CSS = MARCA + r"""
/* Paleta (modelo do dono): carvão #111312 · superfície #1A1D1B · verde-escuro #16241E · areia #C8B288 · off-white #F2EFE9 · cinza #9A9D98.
   Areia é a única cor de destaque; o verde-escuro é a cor dos blocos de ícone, seleção e aviso. */
:root:not([data-theme="light"]),:root[data-theme="dark"]{
  --bg:#111312;--tint:transparent;--surface:#1A1D1B;--surface-2:#222624;--ink:#F2EFE9;--ink-2:#9A9D98;--line:#2A2E2C;
  --brand:#C8B288;--brand-ink:#111312;--brand-soft:#16241E;--gold:#C8B288;--gold-soft:#2A271E;
  --grad:#C8B288;--dark-grad:#16241E;--gold-grad:#C8B288;--glow:none;--shadow:none;--shadow-sm:none;
  --ok:#86BF9B;--ok-soft:#16241E;--warn:#D9B96F;--warn-soft:#2B2616;--bad:#E58F85;--bad-soft:#301C1A;
  --on-photo:#FFFFFF;--scrim:rgba(0,0,0,.7);
  --map-land:#151817;--map-block:#1B1F1D;--map-park:#16241E;--map-water:#142229;
  --r:12px;--r-lg:16px;--font-display:'Plus Jakarta Sans','Inter',system-ui,sans-serif;--font-body:'Inter',system-ui,sans-serif;
  --bar-sombra:0 10px 30px rgba(0,0,0,.5);color-scheme:dark}
:root[data-theme="light"]{
  --bg:#F2EFE9;--tint:transparent;--surface:#FBFAF7;--surface-2:#E9E5DB;--ink:#111312;--ink-2:#5F645F;--line:#DAD5C8;
  --brand:#1E3129;--brand-ink:#F2EFE9;--brand-soft:#E3E0D3;--gold:#7A6636;--gold-soft:#EFE9D8;
  --grad:#1E3129;--dark-grad:#1E3129;--gold-grad:#7A6636;--glow:none;--shadow:none;--shadow-sm:none;
  --ok:#2E6B4E;--ok-soft:#E3ECE2;--warn:#7D5F1E;--warn-soft:#F1EAD6;--bad:#9A4038;--bad-soft:#F3E3DF;
  --on-photo:#FFFFFF;--scrim:rgba(17,19,18,.55);
  --map-land:#E7E3D8;--map-block:#F3F0E8;--map-park:#DCE3D3;--map-water:#D3DEE0;
  --r:12px;--r-lg:16px;--font-display:'Plus Jakarta Sans','Inter',system-ui,sans-serif;--font-body:'Inter',system-ui,sans-serif;
  --bar-sombra:0 8px 24px rgba(17,19,18,.12);color-scheme:light}
body{background-color:var(--bg);background-image:none;font-family:var(--font-body)}
::selection{background:#C8B288;color:#111312}
h1,h2,h3,.top h1,.stat b,.kpis b{font-family:var(--font-display)}
h1,h2,h3{font-weight:600;letter-spacing:-.015em}
.eyebrow,.tag{color:var(--brand)}
/* superfícies: linha fina (hairline), sem sombra */
.card,.pcard,.hrow,.feat,.stat,.field input,.field textarea,.search,.iconbtn{border:1px solid var(--line)}
.pcard,.hrow,.feat,.card{border-radius:var(--r-lg)}
.btn{border-radius:10px;font-weight:600}
.btn.ghost{box-shadow:inset 0 0 0 1px var(--brand)!important}
.chip{border-radius:10px;box-shadow:none!important;border:1px solid var(--line)}
.chip[aria-pressed="true"]{border-color:var(--brand)}
.tabs{background:var(--surface-2);box-shadow:none!important;border:1px solid var(--line)}
/* barra de abas flutuante, nas cores do modelo */
.tabbar{background:var(--surface)!important;border:1px solid var(--line);box-shadow:var(--bar-sombra)!important;-webkit-backdrop-filter:none!important;backdrop-filter:none!important}
.tabbar button{font-size:.66rem;font-weight:500;letter-spacing:.01em;color:var(--ink-2)}
.tabbar button[aria-current="page"]{color:var(--brand);font-weight:600}
.tabbar .i{width:1.4em;height:1.4em}
.ind{background:var(--brand-soft)!important}
/* ícones em bloco verde-escuro com areia */
.cat .c,.ico,.ico.soft,.avatar{background:var(--brand-soft);color:var(--brand)}
.cat .c{box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--brand) 22%,transparent)!important}
/* painel e aviso (modelo: painel na cor da superfície, aviso verde-escuro com borda areia) */
#sheet .scrim{-webkit-backdrop-filter:blur(2px);backdrop-filter:blur(2px)}
#sheet .panel{background:var(--surface);border:1px solid var(--line);border-bottom:0;border-radius:16px 16px 0 0}
@media (min-width:720px){#sheet .panel{border-radius:16px;border-bottom:1px solid var(--line)}}
#sheet .grab{width:36px;height:4px;background:color-mix(in srgb,var(--ink) 18%,transparent)}
#toast{background:var(--brand-soft);color:var(--ink);border:1px solid color-mix(in srgb,var(--brand) 32%,transparent);border-radius:10px;font-size:.8rem;font-weight:500;padding:10px 16px;box-shadow:0 10px 30px rgba(0,0,0,.35)}
/* foto indisponível: bloco verde-escuro com contorno de areia (o texto é só a categoria) */
.tile,.evtile{background:var(--brand-soft);color:var(--brand);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--brand) 24%,transparent)}
.tile{letter-spacing:.16em;text-transform:uppercase;font-size:.66rem;font-weight:600}
.tile .i{opacity:.9}
.ph{background:var(--brand-soft)}
/* perfil: faixa verde-escuro com areia, igual ao modelo */
.phero{background:var(--dark-grad);color:#F2EFE9;border:1px solid color-mix(in srgb,#C8B288 20%,transparent);border-radius:var(--r-lg);box-shadow:none}
.phero::before{background:rgba(200,178,136,.07)}.phero::after{background:rgba(200,178,136,.05)}
.phero .bar{background:rgba(242,239,233,.16)}
.phero .bar>i{background:#C8B288}
.phero .sub,.phero .note{color:rgba(242,239,233,.78)}
.avatar.lg{background:rgba(242,239,233,.12);color:#F2EFE9;box-shadow:0 0 0 2px #C8B288}
.xpnum{background:none;-webkit-background-clip:border-box;background-clip:border-box;color:var(--gold)}
.phero .xpnum{color:#C8B288}
/* controles */
.switch{background:color-mix(in srgb,var(--ink) 20%,var(--surface))}
.switch[aria-checked="true"]{background:var(--brand)}
.stars button{color:color-mix(in srgb,var(--ink) 24%,transparent)}
.stars button.on{color:var(--gold)}
.check{border-color:color-mix(in srgb,var(--ink) 32%,transparent)}
.heart[aria-pressed="true"]{color:var(--brand-ink);background:var(--brand)}
.heart[aria-pressed="true"] .i{fill:currentColor}
/* abertura, leitor de QR e resultados */
.splash{background:#16241E;color:#F2EFE9}.splash .logo-mark{color:#F2EFE9}
.loader{background:rgba(242,239,233,.2)}.loader i{background:#C8B288}
.scan{background:radial-gradient(circle at 50% 40%,#16241E,#0B0C0B 72%)}
.scan .frame i{border-color:#C8B288}.scan .line{background:#C8B288;box-shadow:0 0 14px #C8B288}
.big.ok{background:#2E6B4E}.big.warn{background:#8A7340}.big.bad{background:#9A4038}.big.brand{background:var(--brand);color:var(--brand-ink)}
.lv-badge{background:var(--brand);color:var(--brand-ink)}
.spin{border-top-color:var(--brand)}
.burst i{background:var(--brand)}
@media (hover:hover){
 .btn:not(.ghost):not(.soft):not([disabled]):hover{box-shadow:none;filter:brightness(1.06)}
 .pcard:hover,.hrow:hover,.feat:hover{box-shadow:none;border-color:color-mix(in srgb,var(--brand) 38%,var(--line))}
 .cat:hover .c{box-shadow:none!important}
}
"""

FONTES_NOVAS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400..600'
                '&family=Plus+Jakarta+Sans:wght@500..700&display=swap">')


def main(arq):
    h = open(arq, encoding="utf-8").read()
    if MARCA in h:
        print("já aplicado")
        return
    # 1) fontes (o build de produção troca este <link> pelas fontes locais com hash)
    h, n = re.subn(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/css2\?family=Figtree[^"]*">', FONTES_NOVAS, h, count=1)
    assert n == 1, "link das fontes não encontrado"
    # 2) CSS por último
    i = h.index("</style>")
    h = h[:i] + CSS + h[i:]
    # 3) escuro por padrão (a escolha salva na pessoa continua valendo)
    ant = 'try{const sv=localStorage.getItem(THEME_KEY);applyTheme(sv==="dark"?"dark":"light")}catch(e){applyTheme("light")}'
    assert ant in h, "inicialização do tema não encontrada"
    h = h.replace(ant, 'try{const sv=localStorage.getItem(THEME_KEY);applyTheme(sv==="light"?"light":"dark")}catch(e){applyTheme("dark")}')
    ant2 = 'return document.documentElement.getAttribute("data-theme")||"light"'
    assert ant2 in h
    h = h.replace(ant2, 'return document.documentElement.getAttribute("data-theme")||"dark"')
    # 4) cor da barra do navegador
    if 'name="theme-color"' not in h:
        h = h.replace('<title>TURIZ</title>', '<title>TURIZ</title>\n<meta name="theme-color" content="#111312">', 1)
    open(arq, "w", encoding="utf-8").write(h)
    print("ok")


if __name__ == "__main__":
    main(sys.argv[1])
