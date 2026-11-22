#!/usr/bin/env python3
"""Parte 2: páginas legais (privacidade, termos, armazenamento local, reembolso, imagens, empresa), direitos LGPD (exportar/excluir),
tela de segurança real, aviso de armazenamento local e verificação de sessão. Idempotente."""
import sys
dst = sys.argv[1]
s = open(dst, encoding="utf-8").read()
if "/* ===== LEGAL ===== */" in s:
    print("já aplicado"); sys.exit(0)

def sub(a, b, c=1):
    global s
    assert s.count(a) == c, (a[:80], s.count(a)); s = s.replace(a, b)

LEGAL = r'''/* ===== LEGAL ===== */
/* Textos escritos a partir do que o sistema FAZ de fato (veja docs/seguranca/dados-pessoais.md). São um ponto de partida: precisam de
   revisão jurídica antes do lançamento (o build de produção exige essa confirmação). */
const EMP=k=>esc(EMPRESA[k]||"[a definir]");
const LEGAL_ABAS=[["priv","Privacidade"],["termos","Termos"],["local","Armazenamento"],["reemb","Ingressos"],["img","Imagens"],["emp","Empresa"]];
const LEGAL_DATA="22/11/2026";
const LEGAL={
 priv:()=>`<p class="sub">Última atualização: ${LEGAL_DATA}</p>
 <h2>Quem somos</h2><p>O controlador dos seus dados pessoais é ${EMP("razao")} (CNPJ ${EMP("cnpj")}). Encarregado de dados (LGPD): ${EMP("encarregado")}.</p>
 <h2>Quais dados tratamos e para quê</h2>
 <ul><li><b>Conta:</b> e-mail, nome e senha (guardada só como hash Argon2id; nunca em texto). Para criar e proteger sua conta. Base legal: execução do contrato.</li>
 <li><b>Favoritos e preferências:</b> o que você salva no app. Para personalizar sua experiência.</li>
 <li><b>Sessões e segurança:</b> aparelho/navegador usado e um identificador de IP irreversível (não guardamos o IP). Para detectar acessos suspeitos e evitar fraudes. Base legal: legítimo interesse e prevenção a fraudes. Guardados por até 12 meses.</li>
 <li><b>Localização:</b> só se você permitir no aparelho, para mostrar o que está perto. Ela é usada no próprio aparelho e <b>não é enviada nem guardada</b> pelos nossos servidores.</li>
 <li><b>Câmera e nota fiscal:</b> a câmera só lê o QR Code no aparelho. Guardamos apenas uma impressão digital (hash) da chave da nota para impedir uso duplicado. <b>Não guardamos a nota, nem o CNPJ</b> do estabelecimento.</li></ul>
 <h2>O que não fazemos</h2><p>Não vendemos seus dados, não usamos anúncios, não usamos rastreadores de terceiros nem análise comportamental.</p>
 <h2>Com quem compartilhamos</h2><p>Apenas com prestadores necessários ao funcionamento (hospedagem, envio de e-mail), sob contrato, e com autoridades quando a lei exigir.</p>
 <h2>Seus direitos (LGPD, art. 18)</h2><p>Você pode confirmar a existência de tratamento, acessar, corrigir, exportar, anonimizar, pedir a eliminação, revogar consentimentos e se opor a tratamentos. Em <b>Configurações → Seus dados</b> você exporta e exclui sua conta na hora. Outros pedidos: ${EMP("encarregado")}.</p>
 <h2>Segurança</h2><p>Conexão criptografada (HTTPS), senhas com Argon2id, sessões que expiram, verificação em duas etapas obrigatória para administradores, limites contra ataques automatizados e registros de auditoria. Nenhum sistema é 100% seguro; se houver incidente que afete você, avisaremos conforme a lei.</p>
 <h2>Menores de idade</h2><p>O TURIZ trata de bares, festas e eventos e é destinado a maiores de 18 anos.</p>
 <h2>Mudanças</h2><p>Se esta política mudar de forma relevante, avisaremos no app.</p>`,
 termos:()=>`<p class="sub">Última atualização: ${LEGAL_DATA}</p>
 <h2>O que é o TURIZ</h2><p>Um guia para descobrir restaurantes, bares, festas e eventos. As informações vêm de fontes abertas e de terceiros (como OpenStreetMap, dados públicos e plataformas de eventos) e podem estar desatualizadas ou incompletas. Confirme horários, preços e disponibilidade com o estabelecimento ou o organizador.</p>
 <h2>Sua conta</h2><p>Você é responsável por manter sua senha em segurança e por tudo o que acontece na sua conta. Informe-nos se suspeitar de uso indevido. Podemos limitar ou suspender acessos que indiquem fraude ou abuso, sempre com possibilidade de revisão.</p>
 <h2>Conteúdo e avaliações</h2><p>Avaliações devem refletir experiências reais. Não são permitidas avaliações falsas, ofensivas ou feitas em troca de vantagem não declarada. Podemos moderar e remover conteúdo que viole estes termos.</p>
 <h2>XP, níveis e recompensas</h2><p>O XP depende de experiências comprovadas. Tentativas de fraude (notas repetidas, contas falsas, automação) podem reter o XP e levar à revisão da conta. As regras podem mudar com aviso.</p>
 <h2>Ingressos e compras</h2><p>O TURIZ <b>não vende ingressos</b>. Os links levam ao site oficial do organizador, que responde pela venda, entrega e reembolso.</p>
 <h2>Propriedade intelectual</h2><p>Marca, design e código do TURIZ pertencem à ${EMP("razao")}. Fotos e textos de terceiros pertencem aos respectivos titulares e são exibidos com crédito. Veja a aba Imagens.</p>
 <h2>Limitação de responsabilidade</h2><p>Fazemos o possível para manter as informações corretas, mas não garantimos que estejam sempre atualizadas e não respondemos por decisões tomadas apenas com base nelas, nos limites da lei.</p>
 <h2>Lei aplicável</h2><p>Lei brasileira. Contato: ${EMP("contato")}.</p>`,
 local:()=>`<p class="sub">Última atualização: ${LEGAL_DATA}</p>
 <p>O TURIZ <b>não usa cookies de publicidade nem de rastreamento</b>, e não carrega scripts de terceiros. Usamos apenas o armazenamento essencial do navegador:</p>
 <ul><li><b>turiz_sessao</b> (cookie, HttpOnly): mantém você conectado. Expira em até 30 dias.</li>
 <li><b>turiz_csrf</b> (cookie): protege contra requisições forjadas.</li>
 <li><b>turiz-theme, turiz-motion</b> (armazenamento local): tema claro/escuro e redução de movimento.</li>
 <li><b>turiz-session</b> (armazenamento local): lembra que você já entrou, para abrir direto no início.</li></ul>
 <p>Como são estritamente necessários, não pedem consentimento. Você pode apagá-los quando quiser nas configurações do navegador (isso desconecta você).</p>`,
 reemb:()=>`<p class="sub">Última atualização: ${LEGAL_DATA}</p>
 <p>O TURIZ não vende ingressos nem recebe pagamentos. Ao tocar em “Ingressos no site oficial”, você sai do TURIZ e a compra é feita com o organizador ou a plataforma de venda indicados.</p>
 <p>Cancelamento, adiamento, troca e <b>reembolso</b> seguem a política de quem vendeu o ingresso e a legislação aplicável, incluindo o Código de Defesa do Consumidor. Quando um evento é cancelado ou adiado pela fonte, mostramos o aviso no TURIZ, mas a decisão e o reembolso são do organizador.</p>`,
 img:()=>`<p class="sub">Última atualização: ${LEGAL_DATA}</p>
 <p>Fotos de locais e eventos vêm de sites dos próprios estabelecimentos, de organizadores, de plataformas de eventos e do Wikimedia Commons. Mostramos o crédito e o link da origem. Quando uma foto é apenas ilustrativa, ela vem marcada como “foto ilustrativa”.</p>
 <p>Se você é titular de uma imagem ou responsável por um estabelecimento e quer <b>corrigir ou remover</b> uma foto ou informação, escreva para ${EMP("contato")}. Atendemos o pedido em até ${EMP("prazoRemocao")}.</p>`,
 emp:()=>`<div class="kv-lista"><div class="kv"><span>Razão social</span><b>${EMP("razao")}</b></div><div class="kv"><span>CNPJ</span><b>${EMP("cnpj")}</b></div><div class="kv"><span>Endereço</span><b>${EMP("endereco")}</b></div><div class="kv"><span>Contato</span><b>${EMP("contato")}</b></div><div class="kv"><span>Encarregado de dados (LGPD)</span><b>${EMP("encarregado")}</b></div></div>`
};
S.tab.legal="priv";
V.legal=()=>{const k=S.tab.legal||"priv";return topbar("Privacidade e termos")+segs("legal",LEGAL_ABAS)+`<div class="card pad legal" style="margin-top:14px">${LEGAL[k]()}</div>`};
const legalLinks=`<p class="sub" style="text-align:center;margin-top:14px;font-size:.8rem">Ao continuar, você aceita os <button class="link" data-act="legal:termos">Termos</button> e a <button class="link" data-act="legal:priv">Política de Privacidade</button>.</p>`;
'''
sub('/* ===== MODO PRODUÇÃO ===== */', LEGAL.replace('/* ===== LEGAL ===== */', '/* ===== LEGAL ===== */') + '/* ===== MODO PRODUÇÃO ===== */')
# V e segs/topbar ainda não existem nesse ponto: move o bloco para depois de segs/topbar
i = s.index('/* ===== LEGAL ===== */'); j = s.index('/* ===== MODO PRODUÇÃO ===== */')
bloco = s[i:j]; s = s[:i] + s[j:]
sub('/* ---------- shell + render ---------- */', bloco + '/* ---------- shell + render ---------- */')

# ações
sub('    case"filters":sheet(filterSheet());break;', '    case"filters":sheet(filterSheet());break;\n    case"legal":S.tab.legal=a;go("legal");break;')
sub('S.stack=[];S.auth={mode:"login",err:{},sent:false};go("login",null,true);break;', 'S.stack=[];S.auth={mode:"login",err:{},sent:false};go("login",null,true);break;\n    case"excluirconta":sheet(excluirSheet());break;\n    case"excluirgo":excluirConta();break;')
# links legais: login e configurações
sub('<div class="field"><label for="f-mail">E-mail</label>', '<div class="field"><label for="f-mail">E-mail</label>')
i = s.index('V.login=()=>'); j = s.index('</section>`', i)
s = s[:j] + '${legalLinks}' + s[j:]
sub('<h2 style="font-size:1rem;margin:20px 0 8px">Seus dados</h2>', '<h2 style="font-size:1rem;margin:20px 0 8px">Privacidade e termos</h2><div class="list card">${li("shield","Política de privacidade","Como tratamos seus dados","act:legal:priv")}${li("list","Termos de uso","","act:legal:termos")}${li("gear","Armazenamento local e cookies","Sem rastreadores","act:legal:local")}${li("ticket","Ingressos e reembolso","","act:legal:reemb")}${li("camera","Imagens e remoção","","act:legal:img")}${li("people","Dados da empresa","","act:legal:emp")}</div>\n<h2 style="font-size:1rem;margin:20px 0 8px">Seus dados</h2>')
# excluir conta: sem exemplo em produção
sub('case"delyes":S.ex.del=false;toast("Exemplo: nos dados reais, a exclusão tem prazo e confirmação por e-mail.");render();break;', 'case"delyes":S.ex.del=false;if(PROTO){toast("Exemplo: nos dados reais, a exclusão pede sua senha e apaga tudo na hora.");render()}else sheet(excluirSheet());break;')

# exportar / excluir (LGPD)
EXTRA = r'''
function baixarJson(nome,obj){const b=new Blob([JSON.stringify(obj,null,2)],{type:"application/json"}),a=document.createElement("a");a.href=URL.createObjectURL(b);a.download=nome;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),2000)}
async function exportarDados(){
  if(PROTO){const j=JSON.stringify({aviso:"Protótipo: dados locais de exemplo",favoritos:[...S.fav],preferencias:{cozinhas:[...S.prefs.cuisines]},xp:S.xp},null,2);
    sheet(`<div class="grab"></div><div class="row between"><h2>Seus dados (exemplo)</h2><button class="iconbtn" data-act="close" aria-label="Fechar">${ic("close")}</button></div><p class="sub" style="margin:8px 0">No app de verdade isto vira um arquivo para baixar. Aqui, copie o texto abaixo.</p><textarea readonly rows="10" style="width:100%;font:12px monospace;border:1px solid var(--line);border-radius:10px;padding:10px;background:var(--surface);color:var(--ink)" aria-label="Seus dados em JSON">${esc(j)}</textarea>`);return}
  let r=await api("/conta/exportar");
  if(r.reauth){const senha=prompt("Confirme sua senha para exportar seus dados:");if(!senha)return;const ra=await api("/conta/reautenticar",{method:"POST",body:{senha}});if(!ra.ok){toast("Senha incorreta");return}r=await api("/conta/exportar")}
  if(r.ok){baixarJson("turiz-meus-dados.json",r.j);toast("Seus dados foram baixados")}else toast(msgApi(r,"Não foi possível exportar agora."))}
const excluirSheet=()=>`<div class="grab"></div><div class="row between"><h2>Excluir conta</h2><button class="iconbtn" data-act="close" aria-label="Fechar">${ic("close")}</button></div>
<p class="sub" style="margin:8px 0 12px">Isso apaga sua conta, favoritos, sessões e preferências. Não dá para desfazer. Digite sua senha para confirmar.</p>
<div class="field"><label for="f-del">Senha</label><input id="f-del" type="password" autocomplete="current-password"></div>
<p class="err" id="del-erro" role="alert"></p><button class="btn block" style="background:var(--bad);color:#fff" data-act="excluirgo">Excluir minha conta</button>`;
async function excluirConta(){const senha=$("#f-del")?$("#f-del").value:"";const r=await api("/conta",{method:"DELETE",body:{senha}});
  if(r.ok){closeSheet();remember(false);S.user=null;S.stack=[];S.auth={mode:"login",err:{},sent:false};go("login",null,true);toast("Conta excluída")}else{const e=$("#del-erro");if(e)e.textContent=msgApi(r,"Não foi possível excluir.")}}
/* tela de segurança REAL (produção): sessões ativas, sair de tudo, trocar senha */
if(!PROTO){
  V.security=()=>{if(S.sessApi===undefined){S.sessApi=null;api("/conta/sessoes").then(r=>{S.sessApi=r.ok?r.j:[];if(S.route.n==="security")render()})}
    const ss=S.sessApi||[];
    return topbar("Segurança")+`<div class="card pad"><b>${esc(S.user?S.user.email:"Sua conta")}</b><div class="sub">${S.user&&S.user.mfa_ativo?"Verificação em duas etapas ativa.":"Verificação em duas etapas: obrigatória para administradores."}</div></div>
    <h2 style="font-size:1rem;margin:20px 0 8px">Dispositivos conectados</h2><div class="list card">${ss.length?ss.map(x=>`<div class="li"><span class="ico">${ic("phone")}</span><span class="grow"><b>${esc((x.dispositivo||"Dispositivo").slice(0,60))}</b><div class="sub">Último uso: ${esc(new Date(x.ultimo_uso_em).toLocaleString("pt-BR"))}</div></span>${x.atual?`<span class="pill ok">Este</span>`:`<button class="btn soft" data-act="encerrar:${x.id}">Encerrar</button>`}</div>`).join(""):`<div class="li"><span class="grow sub">Carregando…</span></div>`}</div>
    <div class="row" style="margin-top:14px;gap:10px"><button class="btn soft grow" data-act="senhanova">Trocar senha</button><button class="btn ghost grow" data-act="sairtodos">Sair de todos</button></div>`};
}
const senhaSheet=()=>`<div class="grab"></div><div class="row between"><h2>Trocar senha</h2><button class="iconbtn" data-act="close" aria-label="Fechar">${ic("close")}</button></div>
<div class="field"><label for="f-sa">Senha atual</label><input id="f-sa" type="password" autocomplete="current-password"></div><div class="field"><label for="f-sn">Nova senha (mín. 10 caracteres)</label><input id="f-sn" type="password" autocomplete="new-password"></div>
<p class="err" id="sn-erro" role="alert"></p><button class="btn block" data-act="senhago">Salvar nova senha</button>`;
'''
sub('function startRegister(pid){', EXTRA + 'function startRegister(pid){')
sub('    case"legal":', '''    case"encerrar":api("/conta/sessoes/"+a,{method:"DELETE"}).then(()=>{S.sessApi=undefined;render()});break;
    case"sairtodos":api("/conta/logout-todos",{method:"POST"}).then(()=>{remember(false);S.user=null;S.stack=[];go("login",null,true)});break;
    case"senhanova":sheet(senhaSheet());break;
    case"senhago":{const sa=$("#f-sa").value,sn=$("#f-sn").value;api("/conta/senha",{method:"POST",body:{senha_atual:sa,senha_nova:sn}}).then(r=>{if(r.ok){closeSheet();toast("Senha alterada. Os outros dispositivos foram desconectados.")}else{const e=$("#sn-erro");if(e)e.textContent=msgApi(r,"Não foi possível trocar a senha.")}});break}
    case"legal":''')
# aviso de armazenamento (produção) + verificação de sessão ao abrir
sub('applyDemo(PROTO?demoPref():false);', '''applyDemo(PROTO?demoPref():false);
if(!PROTO){api("/conta/eu").then(r=>{if(r.ok){S.user=r.j}else if(S.route.n!=="login"&&S.route.n!=="splash"){remember(false);S.stack=[];S.auth={mode:"login",err:{},sent:false};go("login",null,true)}})}
const AVISO_KEY="turiz-aviso-local";let avisoVisto=false;try{avisoVisto=localStorage.getItem(AVISO_KEY)==="1"}catch(e){}
if(!PROTO&&!avisoVisto)setTimeout(()=>{toast("O TURIZ não usa rastreadores. Veja em Configurações → Privacidade e termos.");try{localStorage.setItem(AVISO_KEY,"1")}catch(e){}},2500);''')
open(dst, "w", encoding="utf-8").write(s)
print("parte 2 ok")
