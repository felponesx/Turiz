#!/usr/bin/env python3
"""Parte 3: em produção não existem usuários, rankings, recompensas, missões ou notificações FALSAS; o XP não pode ser calculado no
aparelho (qualquer um forjaria). Essas áreas mostram 'Em breve' até a validação existir no servidor. Idempotente."""
import sys
dst = sys.argv[1]
s = open(dst, encoding="utf-8").read()
if "/* ===== PRODUÇÃO SEM SIMULAÇÕES ===== */" in s:
    print("já aplicado"); sys.exit(0)

def sub(a, b, c=1):
    global s
    assert s.count(a) == c, (a[:80], s.count(a)); s = s.replace(a, b)

sub('<h1 style="font-size:1.6rem">Olá, Lucas!</h1>', '<h1 style="font-size:1.6rem">Olá, ${esc(primeiroNome())}!</h1>')
sub('<h1 style="font-size:1.45rem">Lucas Ferreira</h1>', '<h1 style="font-size:1.45rem">${esc(quemSou())}</h1>')
sub('<span class="avatar">L</span><span><b>Lucas Ferreira</b>', '<span class="avatar">${esc(quemSou()[0])}</span><span><b>${esc(quemSou())}</b>')
sub('  route:{n:"splash"},stack:[],xp:4320,pending:0,', '  route:{n:"splash"},stack:[],xp:PROTO?4320:0,pending:0,')
sub('case"register":startRegister(a);break;', 'case"register":if(!PROTO){toast("O registro de experiências com nota fiscal será ativado quando a validação no servidor estiver pronta.");break}startRegister(a);break;')
sub('case"sample":sampleNote();break;', 'case"sample":if(PROTO)sampleNote();break;')
BLOCO = r'''/* ===== PRODUÇÃO SEM SIMULAÇÕES ===== */
const quemSou=()=>PROTO?"Lucas Ferreira":((S.user&&S.user.nome)||(S.user&&S.user.email)||"Você");
const primeiroNome=()=>quemSou().split(" ")[0];
if(!PROTO){
  const emBreve=t=>()=>topbar(t)+`<div class="card state"><div class="big brand">${ic("shield")}</div><h3>Em breve</h3><p class="sub">Esta área será ativada quando a validação no servidor estiver pronta. Até lá, nada aqui é simulado.</p></div>`;
  for(const [n,t] of [["ranking","Ranking"],["rewards","Recompensas"],["missions","Missões"],["notifs","Notificações"],["badges","Conquistas"],["specs","Especializações"],["history","Histórico"]])V[n]=emBreve(t);
}
'''
sub('/* ---------- shell + render ---------- */', BLOCO + '/* ---------- shell + render ---------- */')
open(dst, "w", encoding="utf-8").write(s)
print("parte 3 ok")
