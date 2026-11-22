import sys
dst=sys.argv[1]; s=open(dst,encoding="utf-8").read()
if "/* ===== ACESSIBILIDADE ===== */" in s: print("já aplicado"); sys.exit(0)
def sub(a,b,c=1):
    global s
    assert s.count(a)==c,(a[:80],s.count(a)); s=s.replace(a,b)
for a in ('role="link" aria-label="${esc(e.name)}"','role="link" aria-label="${esc(feat.name)}"','role="link" aria-label="${esc(p.name)}"'):
    s=s.replace(a,'role="link"')            # o nome acessível passa a ser o texto visível do cartão (WCAG 2.5.3)
sub('role="img" aria-label="Mapa de São Paulo com ${items.length} locais"','role="group" aria-label="Mapa de São Paulo com ${items.length} locais"')
i=s.rindex('</style>'); s=s[:i]+':root[data-theme="dark"]{--grad:#7FBDB4}\n@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--grad:#7FBDB4}}\n'+s[i:]
sub('function render(){','/* ===== ACESSIBILIDADE ===== */\ndocument.documentElement.lang="pt-BR";\nfunction render(){')
open(dst,"w",encoding="utf-8").write(s); print("ok")
