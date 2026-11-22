#!/usr/bin/env python3
"""Prepara o turiz.html para dois modos: PROTÓTIPO (padrão; conta admin/admin, dados de exemplo) e PRODUÇÃO (API real, sem exemplos).
Idempotente. O build de produção (build_producao.py) apenas troca PROTO=false e empacota com CSP estrita."""
import sys
dst = sys.argv[1]
s = open(dst, encoding="utf-8").read()
if "/* ===== MODO PRODUÇÃO ===== */" in s:
    print("já aplicado"); sys.exit(0)

def sub(a, b, c=1):
    global s
    assert s.count(a) == c, (a[:80], s.count(a)); s = s.replace(a, b)

CONST = r'''/* ===== MODO PRODUÇÃO ===== */
/* PROTO=true: protótipo (conta de teste, dados de exemplo, simulações). PROTO=false (build de produção): autenticação REAL na API,
   nenhum dado de exemplo, nenhuma simulação. A empresa/encarregado são preenchidos no build; sem eles o build de produção não sai. */
const PROTO=true;
const API_BASE="";
const EMPRESA={razao:"",cnpj:"",endereco:"",contato:"",encarregado:"",prazoRemocao:""};
const jsonSeguro=async r=>{try{return await r.json()}catch(x){return null}};
async function api(path,opt={}){
  const csrf=(document.cookie.match(/(?:^|;\s*)turiz_csrf=([^;]*)/)||[])[1],h={"Content-Type":"application/json"};
  if(csrf)h["X-CSRF-Token"]=decodeURIComponent(csrf);
  try{const r=await fetch(API_BASE+path,{method:opt.method||"GET",credentials:"include",headers:h,body:opt.body?JSON.stringify(opt.body):undefined});
    return{ok:r.ok,status:r.status,j:await jsonSeguro(r),espera:+r.headers.get("retry-after")||0,mfa:r.headers.get("x-mfa")==="necessario",reauth:r.headers.get("x-reauth")==="necessaria"}}
  catch(x){return{ok:false,status:0,j:null,espera:0,mfa:false,reauth:false}}}
const msgApi=(r,pad)=>r.status===429?`Muitas tentativas. Tente de novo em ${r.espera||60} segundos.`:r.status===0?"Sem conexão com o servidor.":(r.j&&typeof r.j.detail==="string"?r.j.detail:pad);
'''
sub('/* ===== SEGURANÇA DOS DADOS EXTERNOS ===== */', CONST + '/* ===== SEGURANÇA DOS DADOS EXTERNOS ===== */')

# 1) sem handlers inline: erro de imagem tratado por um ouvinte único (CSP estrita não permite onerror="...")
sub(' onerror="evImgFail(this)"', '')
sub(' onerror="plImgFail(this)"', '')
sub('window.evImgFail=img=>', 'document.addEventListener("error",e=>{const t=e.target;if(t&&t.tagName==="IMG"&&t.classList.contains("evimg")){t.hasAttribute("data-p")?plImgFail(t):evImgFail(t)}},true);\nwindow.evImgFail=img=>')

# 2) autenticação: protótipo (como antes) ou API real
sub('function submitAuth(e){e.preventDefault();', 'function submitAuthProto(e){e.preventDefault();')
sub('function startRegister(pid){', r'''async function submitAuth(e){e.preventDefault();if(PROTO)return submitAuthProto(e);
  const reg=S.auth.mode==="reg",er={},mail=$("#f-mail").value.trim(),pass=$("#f-pass").value,nome=reg?$("#f-name").value.trim():"",cod=$("#f-code")?$("#f-code").value.trim():"";
  if(reg&&!nome)er.name="Informe seu nome.";
  if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(mail))er.mail="Digite um e-mail válido.";
  if(pass.length<10)er.pass="A senha precisa ter pelo menos 10 caracteres.";
  S.auth.err=er;S.auth.sent=false;if(Object.keys(er).length){render();return}
  if(reg){const r=await api("/conta/cadastro",{method:"POST",body:{email:mail,senha:pass,nome}});
    if(!r.ok){S.auth.err={pass:esc(msgApi(r,"Não foi possível criar a conta."))};render();return}}
  const r=await api("/conta/login",{method:"POST",body:{email:mail,senha:pass,codigo:cod}});
  if(r.ok){S.user=r.j.usuario;remember(true);S.auth.mfa=false;go(reg?"prefs":"home",null,true);return}
  if(r.mfa){S.auth.mfa=true;S.auth.err={code:"Digite o código do seu app autenticador (ou um código de recuperação)."};render();return}
  S.auth.err={pass:esc(r.status===401?"E-mail ou senha incorretos.":msgApi(r,"Não foi possível entrar."))};render()}
function startRegister(pid){''')
sub('''<input id="f-pass" type="password" autocomplete="${reg?"new-password":"current-password"}" placeholder="Mínimo de 8 caracteres">${e.pass?`<span class="err">${e.pass}</span>`:""}</div>''',
    '''<input id="f-pass" type="password" autocomplete="${reg?"new-password":"current-password"}" placeholder="${PROTO?"Mínimo de 8 caracteres":"Mínimo de 10 caracteres"}">${e.pass?`<span class="err">${e.pass}</span>`:""}</div>
  ${a.mfa?`<div class="field"><label for="f-code">Código de verificação</label><input id="f-code" inputmode="numeric" autocomplete="one-time-code" placeholder="000000">${e.code?`<span class="err">${e.code}</span>`:""}</div>`:""}''')
sub('case"logout":remember(false);S.stack=[];', 'case"logout":if(!PROTO)api("/conta/logout",{method:"POST"});S.user=null;remember(false);S.stack=[];')

# 3) produção: sem dados de exemplo e sem simulações
sub('applyDemo(demoPref());', 'applyDemo(PROTO?demoPref():false);')
a = s.index('<h2 style="font-size:1rem;margin:20px 0 8px">Fotos dos locais</h2>')
b = s.index('<h2 style="font-size:1rem;margin:20px 0 8px">Notificações</h2>')
bloco = s[a:b]
s = s[:a] + '${PROTO?`' + bloco.replace('`', '\\`').replace('${', '\\${') + '`:""}' + s[b:]
# (o bloco acima só aparece no protótipo; as chaves ${...} dentro dele foram escapadas e reavaliadas abaixo)
s = s.replace('${PROTO?`' + bloco.replace('`', '\\`').replace('${', '\\${') + '`:""}', '${PROTO?`' + bloco + '`:""}')
sub('case"demo":{', 'case"demo":{if(!PROTO)break;')

# 4) seus dados: exportar e excluir de verdade
sub('data-act="toast:Pedido de exportação registrado (exemplo)">Exportar</button>', 'data-act="exportar">Exportar</button>')
sub('case"delyes":', 'case"exportar":exportarDados();break;\n    case"delyes":')
open("/tmp/_p.txt","w").write("x")
open(dst, "w", encoding="utf-8").write(s)
print("parte 1 ok")
