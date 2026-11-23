#!/usr/bin/env python3
"""Polimento unslop aplicado ao protótipo inteiro (todas as telas), com o identidade Carvão e Areia mantida.

Entrada: o protótipo antes do polimento (turiz.html). Saída: o protótipo polido. Idempotente (marcador).
O que muda: textos pequenos (piso de 11,5 px), caixa-alta e rastreio em rótulos, acento usado só na seleção e no estado,
saudação com exclamação trocada por título de contexto, pontuação de subtítulos, ícones de selo, movimento de elevação no hover.
O que NÃO muda: paleta, Inter e Plus Jakarta Sans, logotipo (.wordmark), layout, seções, ordem, dados e textos de dados reais.
Uso: python3 unslop_sistema.py entrada.html saida.html
Créditos: passes inspirados na skill unslop (Damir Sokolovsky, @heydamir, CC BY 4.0)."""
import re
import sys

MARCA = "/* ===== UNSLOP SISTEMA ===== */"

# ---------- Trocas no markup (cada uma precisa existir pelo menos uma vez) ----------
TROCAS = [
    # Festas: subtítulo sem ponto final e com a identidade do produto
    ('<p class="sub" style="margin:4px 0 14px">Shows, festas, gastronomia e cultura${atualiz?` · dados atualizados em ${atualiz}`:""}.</p>',
     '<p class="sub" style="margin:4px 0 16px">Shows e festas em São Paulo${atualiz?` · dados atualizados em ${atualiz}`:""}</p>'),
    ('placeholder="Ex.: shows hoje em São Paulo · festas no fim de semana"', 'placeholder="Buscar eventos"'),
    ('<span class="m-sand">${reais.length?"Eventos reais"', '<span class="m-kicker">${reais.length?"Eventos reais"'),
    ('<p class="m-count" style="margin:14px 0 4px">', '<p class="m-count" style="margin:16px 0 8px">'),
    # Início: saudação com exclamação vira título de contexto
    ('<h1 class="m-h1">Olá, ${esc(primeiroNome())}!</h1><p class="sub" style="margin:2px 0 14px">Qual será o seu próximo destino?</p>',
     '<h1 class="m-h1">Descoberta real pela cidade</h1><p class="sub" style="margin:2px 0 14px">${esc(primeiroNome())}, qual será o seu próximo destino?</p>'),
    # Selo de foto ilustrativa: rótulo em caixa-alta vira frase normal (o texto segue visível em todas as telas)
    ('<span class="ilus">foto ilustrativa</span>', '<span class="ilus">Foto ilustrativa</span>'),
    # Festas: selo de foto como ícone nas miniaturas (nome acessível preservado)
    ('<div class="ph m-ev-th">${evMedia(e)}</div>',
     '<div class="ph m-ev-th">${evMedia(e).replace(ilusTag,`<span class="ilus-ic" role="img" aria-label="Foto ilustrativa" title="Foto ilustrativa">${ic("info")}</span>`)}</div>'),
    # Festas: preço com "a partir de" em linha pequena acima do valor
    ('${pr?`<span class="m-price${e.free?" free":""}">${esc(pr)}</span>`:""}',
     '${pr?`<span class="m-price${e.free?" free":""}">${/^a partir de /.test(pr)?`<small class="m-from">a partir de</small>${esc(pr.replace(/^a partir de /,""))}`:esc(pr)}</span>`:""}'),
]

# Rótulos "exemplo", "provável" e similares: frase normal, não caixa-alta
TROCAS_GLOBAIS = [
    ('<span class="exm">exemplo</span>', '<span class="exm">Exemplo</span>'),
    (r'<span class=\"exm\">exemplo</span>', r'<span class=\"exm\">Exemplo</span>'),
    ('<span class="exm">provável</span>', '<span class="exm">Provável</span>'),
    ('<span class="exm" style="margin:6px 0 0">avaliação de exemplo', '<span class="exm" style="margin:6px 0 0">Avaliação de exemplo'),
]

# ---------- CSS: Festas (passes validados na cópia) + sistema ----------
CSS = r"""
/* ===== UNSLOP SISTEMA: textos, acento, movimento ===== */
/* Piso de tamanho para texto de leitura (11,5 px) e tamanhos da escala */
.m-meta,.m-tag,.m-nota,.m-sand,.m-hd,.m-hx,.m-hero-k,.m-sh p,.kpis span,.m-xr small,.m-metrics span,.m-count{font-size:.78rem;letter-spacing:0}
.m-tag{font-size:.7rem}
.m-hd,.m-hx,.m-nota,.m-sand{font-size:.75rem}
.m-lk,.kpi-line{font-size:.8rem}
.m-price{font-size:.8rem;font-weight:500;letter-spacing:0}
.m-save{font-size:.75rem;letter-spacing:0}
.tabbar button{font-size:.7rem}
.proto{font-size:.72rem;letter-spacing:0}
.imgcred{font-size:.72rem;letter-spacing:0}
.exm{font-size:.72rem;letter-spacing:0;text-transform:none;font-weight:500}
.ilus{font-size:.72rem;letter-spacing:0;text-transform:none;font-weight:500}
/* Miniaturas pequenas (até 84 px): o selo vira um ponto; o texto segue no DOM para leitor de tela */
.hrow .ilus,.m-thumb .ilus{font-size:0;width:6px;height:6px;padding:0;border-radius:50%;background:#F2EFE9;left:5px;bottom:5px}
.m-tcard h4{font-size:.875rem;font-weight:500;letter-spacing:0}
.m-row h4{font-size:.9rem;font-weight:500;letter-spacing:0}
.pcard h3{letter-spacing:0;font-weight:500}
h3{letter-spacing:0}
.m-sh h3{font-size:.95rem;letter-spacing:0;font-weight:600}

/* Caixa-alta e rastreio só no logotipo (.wordmark). Rótulos viram frase normal */
.eyebrow{font-size:.78rem;font-weight:500;letter-spacing:0;text-transform:none;color:var(--ink-2)}
.tag{font-size:.8rem;letter-spacing:0;text-transform:none;font-weight:400}
.sp-tag{letter-spacing:0;text-transform:none;font-size:.8rem}
.m-up{font-size:.75rem;font-weight:500;letter-spacing:0;text-transform:none;color:var(--ink-2)}
.m-pf .m-up{color:rgba(242,239,233,.78)}
.tile{letter-spacing:0;text-transform:none;font-size:.75rem;font-weight:500}

/* Acento (cor de destaque) só na seleção e no estado. O resto do texto é tinta neutra */
.m-ev-t{color:var(--ink);font-weight:500}
.m-hero-k{color:rgba(242,239,233,.78)}
.m-sand{color:var(--ink-2)}
.m-price.free{color:var(--brand)}
.m-kicker{font-size:.78rem;font-weight:500;letter-spacing:0;color:var(--ink-2)}
.m-from{display:block;font-size:.72rem;font-weight:400;color:var(--ink-2);margin-bottom:2px}
.m-price{text-align:right;background:none;border:0;padding:0;box-shadow:none;font-variant-numeric:tabular-nums}
.m-save{color:var(--ink-2)}
.m-save[aria-pressed="true"]{color:var(--brand)}

/* Selos de foto ilustrativa: círculo com ícone (Festas) */
.ilus-ic{position:absolute;left:4px;bottom:4px;z-index:2;width:20px;height:20px;border-radius:50%;background:rgba(17,19,18,.72);color:#F2EFE9;display:grid;place-items:center}
.ilus-ic .i{width:12px;height:12px;stroke-width:2}
.m-save .i{width:16px;height:16px;stroke-width:1.5}

/* Festas: agenda (espaçamento na grade de 4 px) */
.m-phead{padding-bottom:0;margin-bottom:0}
.tabs.seg[data-seg="parties"]{margin-top:16px}
.evfilters{gap:8px;margin:12px 0 0}
.m-cats{gap:8px}
.m-cats .chip{font-size:.72rem;letter-spacing:0}
.m-ev{gap:16px;padding:16px 0}
.m-ev .grow{display:grid;gap:4px;min-width:0}
.m-ev-r{gap:8px;justify-items:end}
.m-ev-t{font-size:.78rem}
.m-ev h4{font-size:.95rem;font-weight:500;letter-spacing:0;line-height:1.25}
.m-ev .m-meta{margin-top:0}
.m-ev .exm{margin-left:0}
.evtile{background:var(--brand-soft);color:var(--brand)}

/* Movimento: sem elevação, sem zoom e sem escala no hover. Só troca de cor */
@media (hover:hover){
 .pcard:hover,.hrow:hover,.feat:hover{transform:none}
 .pcard:hover .ph .sc,.hrow:hover .ph .sc,.feat:hover .ph .sc{transform:none}
 .btn:not([disabled]):hover{transform:none}
 .cat:hover{transform:none}
 .cat:hover .c{transform:none;filter:none}
 .chip:hover{transform:none}
 .stars button:hover .i{transform:none}
}

/* Fundo: sem brilho radial atrás da abertura */
.sp-glow{display:none}

/* Cartão sem foto: tom liso da marca */
.tile,.evtile{background:var(--brand-soft)}
"""


def aplicar(h: str) -> str:
    if MARCA in h:
        raise SystemExit("já aplicado: use a entrada sem o polimento")
    # 1) trocas de markup (cada uma precisa existir)
    for antigo, novo in TROCAS:
        n = h.count(antigo)
        assert n >= 1, f"trecho não encontrado: {antigo[:70]}"
        h = h.replace(antigo, novo)
    # 2) rótulos de exemplo (podem aparecer em várias telas)
    for antigo, novo in TROCAS_GLOBAIS:
        h = h.replace(antigo, novo)
    # 3) pontuação: subtítulo de uma frase não termina com ponto (parágrafos de várias frases mantêm)
    h, n_pontos = re.subn(r'(class="sub"[^>]*>)([^<${}`.]*[^<${}`.\s])\.(</)', r"\1\2\3", h)
    # 4) CSS antes do primeiro </style>
    k = h.index("</style>")
    h = h[:k] + MARCA + CSS + h[k:]
    print(f"pontos finais removidos de subtítulos: {n_pontos}")
    return h


if __name__ == "__main__":
    entrada, saida = sys.argv[1], sys.argv[2]
    texto = open(entrada, encoding="utf-8").read()
    open(saida, "w", encoding="utf-8").write(aplicar(texto))
    print("ok:", saida)
