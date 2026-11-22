#!/usr/bin/env python3
"""Tela de abertura (Splash) na identidade Carvão e Areia.

Fundo carvão com um brilho verde-escuro, anéis de areia que se expandem como um radar de localização (a ideia de "descoberta urbana"),
logotipo (o mesmo, só na cor areia), nome, frase e uma linha de progresso. Sempre escura, em qualquer tema. Sem movimento quando a pessoa
pede menos animação (a tela fica estática e segue mais rápido). Idempotente. Uso: python3 patch_splash.py turiz.html"""
import re
import sys

MARCA = "/* ===== SPLASH ===== */"

CSS = MARCA + r"""
.splash{background:#111312;color:#F2EFE9;min-height:100vh;min-height:100dvh;isolation:isolate;text-align:center;
  padding:max(24px,env(safe-area-inset-top)) 24px max(24px,env(safe-area-inset-bottom))}
.splash .sc-bg{display:none}
.sp-glow{position:absolute;inset:0;z-index:-2;background:radial-gradient(62% 46% at 50% 42%,#16241E 0%,rgba(22,36,30,0) 100%),radial-gradient(46% 26% at 50% 104%,rgba(200,178,136,.08),rgba(200,178,136,0))}
.sp-logo{position:relative;display:grid;justify-items:center}
.sp-rings{position:absolute;left:50%;top:50%;width:0;height:0;z-index:-1;pointer-events:none}
.sp-rings i{position:absolute;left:-160px;top:-160px;width:320px;height:320px;border-radius:50%;border:1px solid rgba(200,178,136,.26);opacity:0;transform:scale(.3);animation:sp-ring 3.9s cubic-bezier(.2,.7,.2,1) infinite}
.sp-rings i:nth-child(2){animation-delay:1.3s}.sp-rings i:nth-child(3){animation-delay:2.6s}
@keyframes sp-ring{0%{opacity:0;transform:scale(.3)}14%{opacity:1}100%{opacity:0;transform:scale(2.7)}}
.splash .splash-in{gap:0;justify-items:center;margin-top:-6vh}
.splash .logo-mark{width:92px;color:#C8B288;filter:none}
.sp-logo .logo-mark{animation:sp-up .9s cubic-bezier(.2,.8,.2,1) both}
.sp-word{font-size:2.05rem;margin:18px 0 0;padding-left:.34em;letter-spacing:.34em;color:#F2EFE9;animation:sp-up .9s .25s cubic-bezier(.2,.8,.2,1) both}
.sp-tag{margin-top:12px;padding-left:.22em;color:#C8B288;font-size:.72rem;letter-spacing:.22em;animation:sp-fade 1s .65s ease both}
@keyframes sp-up{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@keyframes sp-fade{from{opacity:0}to{opacity:1}}
.sp-foot{position:absolute;left:0;right:0;bottom:calc(34px + env(safe-area-inset-bottom));display:grid;justify-items:center;gap:6px}
.splash .loader{width:132px;height:2px;margin:0;border-radius:2px;background:rgba(242,239,233,.14)}
.splash .loader i{width:100%;border-radius:2px;background:#C8B288;transform-origin:left center;animation:sp-load 2.2s cubic-bezier(.3,.1,.2,1) both}
@keyframes sp-load{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.sp-skip{border:0;background:none;color:#C8B288;font-weight:600;font-size:.9rem;min-height:44px;padding:10px 20px;border-radius:10px;animation:sp-fade .6s 1.2s ease both}
.sp-skip:hover{background:rgba(200,178,136,.1)}
.sp-skip:focus-visible{outline:2px solid #C8B288;outline-offset:2px}
@media (min-width:720px){.sp-word{font-size:2.4rem}.splash .logo-mark{width:112px}}
@media (max-height:520px){.splash .splash-in{margin-top:-10vh}.sp-foot{bottom:12px}.sp-word{margin-top:10px}}
"""

NOVO = ('V.splash=()=>`<section class="flow splash" aria-label="TURIZ"><div class="sp-glow" aria-hidden="true"></div>'
        '<div class="splash-in"><div class="sp-logo"><div class="sp-rings" aria-hidden="true"><i></i><i></i><i></i></div>${logo()}</div><h1 class="wordmark sp-word">TURIZ</h1>'
        '<p class="tag sp-tag">Descubra. Experimente. Viva.</p></div>'
        '<div class="sp-foot"><div class="loader" aria-hidden="true"><i></i></div><button class="sp-skip" data-act="skip">Entrar</button></div></section>`;')

TEMPO_ANT = 'S._st=setTimeout(()=>{if(S.route.n==="splash")go("login",null,true)},2400)'
TEMPO_NOVO = ('S._st=setTimeout(()=>{if(S.route.n==="splash")go("login",null,true)},'
              '(matchMedia("(prefers-reduced-motion:reduce)").matches||document.documentElement.getAttribute("data-motion")==="reduced")?1200:2400)')


def main(arq):
    h = open(arq, encoding="utf-8").read()
    if MARCA in h:
        print("já aplicado")
        return
    h, n = re.subn(r"V\.splash=\(\)=>`.*?`;", lambda m: NOVO, h, count=1, flags=re.S)
    assert n == 1, "V.splash não encontrado"
    assert TEMPO_ANT in h, "temporizador da abertura não encontrado"
    h = h.replace(TEMPO_ANT, TEMPO_NOVO)
    i = h.index("</style>")
    h = h[:i] + CSS + h[i:]
    open(arq, "w", encoding="utf-8").write(h)
    print("ok")


if __name__ == "__main__":
    main(sys.argv[1])
