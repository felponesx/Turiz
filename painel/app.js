/* Central de bots do Turiz — app estático para o celular. Sem frameworks; todo texto de fora entra por textContent (sem innerHTML). */
(() => {
"use strict";
const REG = window.BOTS_REGISTRY || { grupos: [], bots: [] };
const PARAMS = new URLSearchParams(location.search);
const PADRAO = { repo: "felponesx/Turiz", branch: "bot-status", dados: "main", token: "" };
const $main = document.getElementById("main");
const STALE_MIN = 20;                       // "rodando" sem sinal há mais que isso = provavelmente interrompido

/* ---------- utilidades ---------- */
const lerCfg = () => { try { return { ...PADRAO, ...JSON.parse(localStorage.getItem("turiz-painel") || "{}") }; } catch { return { ...PADRAO }; } };
const salvarCfg = (c) => { try { localStorage.setItem("turiz-painel", JSON.stringify(c)); } catch { /* sem armazenamento: só vale nesta sessão */ } };
let cfg = lerCfg();
if (PARAMS.get("repo")) cfg.repo = PARAMS.get("repo");

function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : document.createTextNode(String(c)));
  return el;
}
const ICONES = {
  pin: '<path d="M12 21s6.5-5.6 6.5-11a6.5 6.5 0 1 0-13 0c0 5.4 6.5 11 6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
  building: '<path d="M5 21V5l9-2v18M14 8h5v13M3 21h18M8 8h2M8 12h2M8 16h2"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  star: '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
  map: '<path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2zM9 4v14M15 6v14"/>',
  image: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M4 17l5-4.5 3.5 3 3-2.5 4.5 4"/>',
  share: '<circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.2 10.8l7.6-3.6M8.2 13.2l7.6 3.6"/>',
  menu: '<path d="M7 3v7a2 2 0 0 0 4 0V3M9 10v11M16 21V3c-2 2-3 5-3 8h3"/>',
  photo: '<path d="M4 8h3l1.5-2h7L17 8h3v11H4z"/><circle cx="12" cy="13.5" r="3.5"/>',
  calendar: '<rect x="4" y="5.5" width="16" height="14.5" rx="2"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
  rocket: '<path d="M5 19c0-4 1-7 4-10s7-4.5 10-4.5c0 3-1.5 7-4.5 10s-6 4-9.5 4.5zM9.5 14.5l-3 3M14.5 9.5a1.3 1.3 0 1 0 0 .01"/>',
  home: '<path d="M3 11l9-7.5L21 11M5.5 9.5V20h13V9.5M10 20v-6h4v6"/>',
  dados: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>',
  back: '<path d="M15 5l-7 7 7 7"/>',
  play: '<path d="M8 5l11 7-11 7z"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v5H5V6h5"/>',
};
function icone(nome) { const s = document.createElementNS("http://www.w3.org/2000/svg", "svg"); s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("class", "i"); s.setAttribute("aria-hidden", "true"); s.innerHTML = ICONES[nome] || ICONES.globe; return s; }
const num = (n) => (n == null || isNaN(n)) ? "–" : Number(n).toLocaleString("pt-BR");
function quando(iso) {
  if (!iso) return "nunca";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 45) return "agora"; if (s < 3600) return `há ${Math.round(s / 60)} min`;
  if (s < 86400) return `há ${Math.round(s / 3600)} h`; return `há ${Math.round(s / 86400)} d`;
}
const hora = (iso) => { try { return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }); } catch { return ""; } };
const seguro = (u) => (typeof u === "string" && /^https:\/\/[^\s"'<>]+$/.test(u)) ? u : null;
let avisoTimer;
function aviso(txt) { const a = document.getElementById("aviso"); a.textContent = txt; a.classList.add("on"); clearTimeout(avisoTimer); avisoTimer = setTimeout(() => a.classList.remove("on"), 3800); }

/* ---------- estado dos bots ---------- */
const ROTULO = { externo: "Automático", rodando: "Rodando", concluido: "Concluído", avisos: "Concluído com avisos", erro: "Erro", aguardando_credencial: "Aguardando chave", aguardando_config: "Aguardando ajuste", semsinal: "Sem sinal", nunca: "Ainda não rodou", ocioso: "Parado" };
const ST = {};                // id -> status do bot (ou null = nunca rodou)
let redeErro = false, ultimaBusca = 0, buscando = false;

function efetivo(s) {
  if (!s) return "nunca";
  if (s.estado === "rodando" && s.atualizado_em && (Date.now() - new Date(s.atualizado_em).getTime()) / 60000 > STALE_MIN) return "semsinal";
  return s.estado || "ocioso";
}
async function buscarStatus(id) {
  const base = PARAMS.get("base");
  let url, init = { cache: "no-store" };
  if (base) url = `${base}${id}.json`;
  else if (cfg.token) { url = `https://api.github.com/repos/${cfg.repo}/contents/status/${id}.json?ref=${cfg.branch}`; init.headers = { Authorization: `Bearer ${cfg.token}`, Accept: "application/vnd.github.raw+json" }; }
  else url = `https://raw.githubusercontent.com/${cfg.repo}/${cfg.branch}/status/${id}.json?t=${Date.now()}`;
  const r = await fetch(url, init);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}
async function atualizar(manual) {
  if (buscando) return; buscando = true;
  const btn = document.getElementById("btn-atualizar"); btn.classList.add("gira");
  let falhas = 0;
  await Promise.all(REG.bots.map(async (b) => {
    try {
      ST[b.id] = await buscarStatus(b.id);
      if (!ST[b.id] && b.externo) ST[b.id] = { estado: "externo", percentual: 0, mensagem: "Roda sozinho todo dia às 11:07 (Brasília) e avisa por notificação no celular." };
    } catch { falhas++; }
  }));
  redeErro = falhas === REG.bots.length; ultimaBusca = Date.now(); buscando = false;
  btn.classList.remove("gira");
  if (manual && redeErro) aviso("Sem conexão com o GitHub. Mostrando o último estado conhecido.");
  if (rota().tela !== "ajustes") desenhar();
}
const algumRodando = () => REG.bots.some((b) => efetivo(ST[b.id]) === "rodando");

/* ---------- componentes ---------- */
function barra(pct) { return h("div", { class: "barra", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": 100, "aria-valuenow": pct }, h("i", { style: `width:${Math.max(0, Math.min(100, pct))}%` })); }
const ROT_CONTA = { captados: "Captados", novos: "Novos", atualizados: "Atualizados", falhas: "Falhas", bloqueados: "Bloqueados (robots)", completados: "Completados", consultados: "Consultados", pendentes: "Pendentes",
  baixadas: "Baixadas", ja_existiam: "Já existiam", duplicados: "Duplicados", candidatos: "Candidatos", sites_para_visitar: "Sites a visitar", lugares_para_visitar: "Lugares a visitar", para_processar: "A processar", fotos: "Fotos" };
const ROT_TOTAL = { lugares: "Lugares", eventos: "Eventos", imagens: "Imagens", vinculos: "Redes sociais", cardapios: "Cardápios", fotos: "Fotos", fotos_ilustrativas: "Fotos ilustrativas", lugares_receita: "Lugares da Receita",
  com_bairro: "Com bairro", com_cep: "Com CEP", com_rua: "Com rua", confirmados: "Confirmados", lugares_com_imagem: "Lugares com imagem", lugares_com_rede: "Lugares com rede", fontes: "Fontes", temas: "Temas", tamanho_kb: "KB de fotos" };
const bonito = (k) => k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

function minis(contagem) {
  const itens = Object.entries(contagem || {}).filter(([, v]) => typeof v === "number" && v > 0).slice(0, 4);
  return itens.length ? h("div", { class: "minis" }, itens.map(([k, v]) => h("span", {}, `${ROT_CONTA[k] || bonito(k)} `, h("b", { text: num(v) })))) : null;
}
function cartao(b) {
  const s = ST[b.id], e = efetivo(s);
  const pct = s ? (s.percentual || 0) : 0;
  let linha;
  if (e === "rodando") linha = h("div", { class: "captando" }, h("em", { text: "Captando agora: " }), s.atual || s.etapa || "iniciando…");
  else if (e === "externo") linha = h("div", { class: "captando" }, s.mensagem);
  else if (e === "nunca") linha = h("div", { class: "captando" }, h("em", { text: b.agenda ? `Agenda: ${b.agenda}` : "Ainda não rodou" }));
  else linha = h("div", { class: "captando" }, h("em", { text: `Último resultado ${quando(s.finalizado_em || s.atualizado_em)}${s.mensagem ? " — " : ""}` }), s.mensagem || "");
  return h("a", { class: `cartao est-${e}`, href: `#/bot/${b.id}`, "aria-label": `${b.nome}: ${ROTULO[e]}, ${pct}%` },
    h("div", { class: "cabeca" }, h("div", { class: "ic" }, icone(b.icone)), h("div", { class: "titulo" }, h("b", { text: b.nome }), h("small", { text: b.fonte })), h("span", { class: "selo", text: ROTULO[e] })),
    e === "externo" ? null : barra(e === "nunca" ? 0 : pct),
    e === "externo" ? null : h("div", { class: "linha-p" }, h("span", {}, s && s.etapa && e === "rodando" ? s.etapa : (s && s.iniciado_em ? `Iniciou ${quando(s.iniciado_em)}` : "")), h("b", { text: e === "nunca" ? "" : pct + "%" })),
    linha, s ? minis(s.contagem) : null);
}

/* ---------- telas ---------- */
function telaInicio() {
  const cont = { rodando: 0, ok: 0, atencao: 0, espera: 0 };
  for (const b of REG.bots) { const e = efetivo(ST[b.id]); if (e === "rodando") cont.rodando++; else if (e === "concluido") cont.ok++; else if (["erro", "avisos", "semsinal"].includes(e)) cont.atencao++; else if (e.startsWith("aguardando")) cont.espera++; }
  const tot = (chave, ...bots) => Math.max(0, ...bots.map((id) => (ST[id] && ST[id].totais && ST[id].totais[chave]) || 0));
  const raiz = h("div", {});
  if (redeErro) raiz.append(h("div", { class: "alerta" }, h("b", { text: "Sem conexão" }), "Não consegui falar com o GitHub agora; o que aparece pode estar desatualizado."));
  raiz.append(h("div", { class: "resumo" },
    h("div", { class: "chip-n run" }, h("b", { text: cont.rodando }), h("span", { text: "rodando" })), h("div", { class: "chip-n ok" }, h("b", { text: cont.ok }), h("span", { text: "ok" })),
    h("div", { class: "chip-n warn" }, h("b", { text: cont.espera }), h("span", { text: "esperando" })), h("div", { class: "chip-n err" }, h("b", { text: cont.atencao }), h("span", { text: "atenção" }))));
  raiz.append(h("div", { class: "secao" }, h("h2", { text: "Dentro do sistema Turiz" }), h("div", { class: "kpis" },
    kpi("Lugares", Math.max(tot("lugares", "osm", "enderecos", "sites", "google"))), kpi("Eventos", tot("eventos", "eventos")), kpi("Imagens", tot("imagens", "imagens")),
    kpi("Redes sociais", tot("vinculos", "instagram")), kpi("Cardápios", tot("cardapios", "cardapios")), kpi("Fotos", tot("fotos", "fotos")))));
  const precisa = REG.bots.filter((b) => ["erro", "aguardando_credencial", "aguardando_config", "semsinal"].includes(efetivo(ST[b.id])));
  if (precisa.length) raiz.append(h("div", { class: "secao" }, h("h2", { text: "Precisa de você" }), precisa.map((b) => {
    const s = ST[b.id], e = efetivo(s);
    return h("a", { class: "alerta", href: `#/bot/${b.id}`, style: "display:block;text-decoration:none;color:inherit" }, h("b", { text: `${b.nome} — ${ROTULO[e]}` }), (s && s.mensagem) || (e === "semsinal" ? "Parou de dar sinal; talvez tenha sido interrompido." : ""));
  })));
  for (const g of REG.grupos) {
    const bs = REG.bots.filter((b) => b.grupo === g);
    if (bs.length) raiz.append(h("div", { class: "secao" }, h("h2", { text: g }), bs.map(cartao)));
  }
  raiz.append(h("div", { class: "acoes" }, h("button", { class: "btn prim", onclick: () => rodarTudo() }, icone("play"), "Rodar tudo agora")));
  raiz.append(h("p", { class: "dica", text: ultimaBusca ? `Atualizado ${quando(new Date(ultimaBusca).toISOString())}. Atualiza sozinho.` : "" }));
  return raiz;
}
const kpi = (rot, v) => h("div", { class: "kpi" }, h("b", { text: num(v) }), h("span", { text: rot }));

const abertos = new Set();
function detalhe(id) {
  const b = REG.bots.find((x) => x.id === id);
  if (!b) return h("p", { class: "vazio", text: "Bot não encontrado." });
  const s = ST[id], e = efetivo(s), pct = s ? (s.percentual || 0) : 0;
  const raiz = h("div", { class: `est-${e}` });
  raiz.append(h("a", { class: "voltar", href: "#/" }, icone("back"), "Todos os bots"));
  raiz.append(h("div", { class: "cabeca", style: "margin:6px 0 4px" }, h("div", { class: "ic" }, icone(b.icone)), h("div", { class: "titulo" }, h("h1", { style: "font-size:1.3rem", text: b.nome }), h("small", { text: b.fonte })), h("span", { class: "selo", text: ROTULO[e] })));
  raiz.append(h("p", { class: "desc", text: b.descricao }));
  raiz.append(h("div", { class: "cartao", style: "cursor:default" },
    h("div", { class: "linha-p" }, h("span", { text: e === "nunca" ? "Ainda não rodou" : e === "externo" ? "Automático" : (s.etapa || "Progresso") }), h("span", { class: "grande", text: e === "nunca" || e === "externo" ? "–" : pct + "%" })),
    e === "externo" ? null : barra(e === "nunca" ? 0 : pct),
    e === "rodando" ? h("div", { class: "captando" }, h("em", { text: "Captando agora: " }), s.atual || "iniciando…") : null,
    s && s.total ? h("div", { class: "linha-p" }, h("span", { text: "Itens" }), h("b", { text: `${num(s.feitos)} de ${num(s.total)}` })) : null,
    s ? h("div", { class: "linha-p" }, h("span", { text: "Última atualização" }), h("b", { text: quando(s.atualizado_em) })) : null,
    s && s.mensagem ? h("p", { class: "desc", style: "margin-bottom:0", text: s.mensagem }) : null));
  const botoes = h("div", { class: "acoes" });
  if (b.workflow) botoes.append(h("button", { class: "btn prim", onclick: () => rodar(b) }, icone("play"), e === "rodando" ? "Rodar de novo" : "Rodar agora"));
  else botoes.append(h("p", { class: "dica", text: `Roda sozinho: ${b.agenda}.` }));
  if (e === "rodando" && s.run_url) botoes.append(h("button", { class: "btn", onclick: () => cancelar(s) }, icone("stop"), "Cancelar"));
  const link = s && seguro(s.run_url); if (link) botoes.append(h("a", { class: "btn", href: link, target: "_blank", rel: "noopener" }, icone("ext"), "Ver no GitHub"));
  raiz.append(botoes);
  raiz.append(h("p", { class: "dica", text: `Agenda: ${b.agenda}.${b.requer.length ? " Precisa de: " + b.requer.join(", ") + "." : ""}${b.encadeia ? " Quando termina, o próximo bot da cadeia começa sozinho." : ""}` }));
  if (s && s.contagem && Object.keys(s.contagem).length) raiz.append(h("div", { class: "secao" }, h("h2", { text: "Quantos captou" }), h("div", { class: "grade" }, Object.entries(s.contagem).map(([k, v]) => kpi(ROT_CONTA[k] || bonito(k), v)))));
  if (s && s.totais && Object.keys(s.totais).length) raiz.append(h("div", { class: "secao" }, h("h2", { text: "Total no sistema Turiz" }), h("div", { class: "grade" }, Object.entries(s.totais).map(([k, v]) => kpi(ROT_TOTAL[k] || bonito(k), v)))));
  if (s && s.fontes && s.fontes.length) raiz.append(h("div", { class: "secao" }, h("h2", { text: `Fontes (${s.fontes.length})` }), h("div", { class: "lista" }, s.fontes.map((f) =>
    h("div", {}, h("span", {}, h("b", { text: f.nome }), f.mensagem ? h("div", { class: "dica", text: f.mensagem }) : null, f.novos != null ? h("div", { class: "dica", text: `${num(f.coletados)} coletados · ${num(f.novos)} novos` }) : null), h("small", { text: f.estado }))))));
  raiz.append(h("div", { class: "secao" }, h("h2", { text: "O que está sendo captado" }), s && s.itens && s.itens.length
    ? h("div", { class: "lista" }, s.itens.slice(0, 20).map((i) => h("div", {}, h("span", { text: i.txt }), h("small", { text: hora(i.t) }))))
    : h("div", { class: "lista" }, h("div", { class: "vazio", text: e === "nunca" ? "Quando o bot rodar, o que ele captar aparece aqui em tempo real." : "Nada novo nesta execução." }))));
  if (s && s.avisos && s.avisos.length) raiz.append(h("div", { class: "secao" }, h("h2", { text: "Avisos" }), h("div", { class: "lista" }, s.avisos.map((a) => h("div", {}, h("span", { text: a }))))));
  if (s && s.log && s.log.length) raiz.append(detalhes("log", "Registro (log)", h("div", { class: "log", id: "log-caixa", text: s.log.map((l) => `${hora(l.t)}  ${l.txt}`).join("\n") })));
  if (s && s.historico && s.historico.length) raiz.append(detalhes("hist", `Últimas execuções (${s.historico.length})`, h("div", { class: "lista", style: "margin-bottom:12px" }, s.historico.map((x) => {
    const l = seguro(x.run_url); return h("div", {}, h("span", {}, h("b", { text: ROTULO[x.estado] || x.estado }), h("div", { class: "dica", text: (x.mensagem || "") + (x.contagem && x.contagem.novos ? ` · ${x.contagem.novos} novos` : "") })), l ? h("a", { href: l, target: "_blank", rel: "noopener", text: quando(x.fim) }) : h("small", { text: quando(x.fim) }));
  }))));
  return raiz;
}
function detalhes(chave, titulo, conteudo) {
  const d = h("details", {}, h("summary", { text: titulo }), conteudo);
  if (abertos.has(chave)) d.open = true;
  d.addEventListener("toggle", () => { d.open ? abertos.add(chave) : abertos.delete(chave); });
  return d;
}
function telaDados() {
  const raiz = h("div", {}, h("div", { class: "secao", style: "margin-top:0" }, h("h2", { text: "O que cada bot já guardou no sistema" })));
  const lista = h("div", { class: "lista" });
  for (const b of REG.bots) {
    const t = ST[b.id] && ST[b.id].totais;
    if (!t || !Object.keys(t).length) continue;
    lista.append(h("div", { style: "display:block" }, h("b", { text: b.nome }), h("div", { class: "minis" }, Object.entries(t).map(([k, v]) => h("span", {}, `${ROT_TOTAL[k] || bonito(k)} `, h("b", { text: num(v) }))))));
  }
  if (!lista.children.length) lista.append(h("div", { class: "vazio", text: "Os totais aparecem depois da primeira execução de cada bot." }));
  raiz.append(lista);
  raiz.append(h("div", { class: "secao" }, h("h2", { text: "Arquivos de dados" }), h("div", { class: "lista" }, REG.bots.flatMap((b) => b.saidas).filter((v, i, a) => a.indexOf(v) === i).map((p) =>
    h("div", {}, h("span", { text: p }), h("a", { href: `https://github.com/${cfg.repo}/blob/${cfg.dados}/${p}`, target: "_blank", rel: "noopener", text: "abrir" }))))));
  raiz.append(h("p", { class: "dica", text: "Tudo que os bots captam entra direto no sistema Turiz, sem aprovação. O app Turiz recebe esses dados automaticamente todo dia." }));
  return raiz;
}

/* ---------- ações no GitHub (precisam do token) ---------- */
async function gh(caminho, opcoes = {}) {
  const r = await fetch(`https://api.github.com${caminho}`, { ...opcoes, headers: { Authorization: `Bearer ${cfg.token}`, Accept: "application/vnd.github+json", ...(opcoes.headers || {}) } });
  return r;
}
const ENTRADAS = { osm: { fontes: "osm" }, sites: { fontes: "sites" }, eventos: { forcar: "true" } };
function exigirToken() { if (cfg.token) return true; aviso("Para rodar daqui, cole o token do GitHub em Ajustes."); location.hash = "#/ajustes"; return false; }
async function disparar(workflow, inputs) {
  const r = await gh(`/repos/${cfg.repo}/actions/workflows/${workflow}/dispatches`, { method: "POST", body: JSON.stringify({ ref: cfg.dados, ...(inputs ? { inputs } : {}) }) });
  if (r.status !== 204) throw new Error(r.status === 403 || r.status === 404 ? "O token não tem permissão de Actions (leitura e escrita)." : `GitHub respondeu ${r.status}`);
}
async function rodar(b) {
  if (!exigirToken()) return;
  try { await disparar(b.workflow, ENTRADAS[b.id]); aviso(`Pedido enviado: ${b.nome}. Começa em instantes.`); setTimeout(() => atualizar(), 9000); setTimeout(() => atualizar(), 25000); }
  catch (e) { aviso(e.message); }
}
async function rodarTudo() {
  if (!exigirToken()) return;
  try { await disparar("coleta.yml", { fontes: "osm sites ticketmaster" }); await disparar("eventos.yml", { forcar: "true" }); aviso("Pedido enviado: coleta completa e eventos."); setTimeout(() => atualizar(), 9000); }
  catch (e) { aviso(e.message); }
}
async function cancelar(s) {
  if (!exigirToken()) return;
  const m = /\/actions\/runs\/(\d+)/.exec(s.run_url || ""); if (!m) return aviso("Não achei a execução para cancelar.");
  const r = await gh(`/repos/${cfg.repo}/actions/runs/${m[1]}/cancel`, { method: "POST" });
  aviso(r.status === 202 ? "Cancelamento pedido." : `Não consegui cancelar (${r.status}).`);
  setTimeout(() => atualizar(), 6000);
}

/* ---------- ajustes ---------- */
function telaAjustes() {
  const repo = h("input", { id: "f-repo", value: cfg.repo, autocapitalize: "none", autocomplete: "off", spellcheck: "false" });
  const tok = h("input", { id: "f-tok", type: "password", value: cfg.token, placeholder: "github_pat_…", autocomplete: "off", spellcheck: "false" });
  const raiz = h("div", {}, h("h2", { style: "margin-bottom:4px", text: "Conexão com o GitHub" }),
    h("label", { for: "f-repo", text: "Repositório" }), repo,
    h("label", { for: "f-tok", text: "Token do GitHub (opcional)" }), tok,
    h("p", { class: "dica", text: "Sem token você só acompanha. Com token também roda e cancela bots e adiciona fontes de eventos. Crie em GitHub → Settings → Developer settings → Fine-grained tokens, só para este repositório, com Actions: leitura e escrita e Contents: leitura e escrita. Fica guardado só neste aparelho." }),
    h("div", { class: "acoes" },
      h("button", { class: "btn prim", onclick: async () => { cfg = { ...cfg, repo: repo.value.trim(), token: tok.value.trim() }; salvarCfg(cfg); aviso("Salvo."); atualizar(true); } }, "Salvar"),
      h("button", { class: "btn", onclick: async () => {
        cfg = { ...cfg, repo: repo.value.trim(), token: tok.value.trim() };
        try { const r = await fetch(`https://api.github.com/repos/${cfg.repo}`, cfg.token ? { headers: { Authorization: `Bearer ${cfg.token}` } } : {}); aviso(r.ok ? "Conexão ok." : `GitHub respondeu ${r.status}.`); } catch { aviso("Sem conexão com o GitHub."); }
      } }, "Testar")));
  raiz.append(h("h2", { style: "margin:28px 0 4px", text: "Adicionar site de eventos" }), formFonte());
  return raiz;
}
function formFonte() {
  const url = h("input", { id: "f-url", placeholder: "https://site-de-eventos.com.br/agenda", inputmode: "url", autocapitalize: "none" });
  const nome = h("input", { id: "f-nome", placeholder: "Nome da fonte (ex.: Agenda do Sesc)" });
  const lista = h("input", { id: "f-lista", type: "checkbox" });
  const padrao = h("input", { id: "f-padrao", placeholder: "Padrão dos links, ex.: ^/evento/", autocapitalize: "none" });
  const ok = h("input", { id: "f-ok", type: "checkbox" });
  return h("div", {},
    h("p", { class: "dica", text: "O bot lê os dados estruturados (schema.org) das páginas e respeita o robots.txt do site. Se o site bloquear robôs, a fonte aparece como bloqueada." }),
    h("label", { for: "f-url", text: "Endereço da página" }), url, h("label", { for: "f-nome", text: "Nome" }), nome,
    h("div", { class: "cx" }, lista, h("label", { for: "f-lista", style: "margin:0", text: "É uma lista: seguir o link de cada evento" })), padrao,
    h("div", { class: "cx" }, ok, h("label", { for: "f-ok", style: "margin:0", text: "Posso coletar eventos deste site" })),
    h("div", { class: "acoes" }, h("button", { class: "btn prim", onclick: () => adicionarFonte({ url: url.value.trim(), nome: nome.value.trim(), lista: lista.checked, padrao: padrao.value.trim(), ok: ok.checked }) }, "Adicionar fonte")));
}
function trechoFonte(f) {
  const u = new URL(f.url);
  if (u.protocol !== "https:") throw new Error("Use um endereço https://");
  if (!/^[\w.\-]+$/.test(u.hostname)) throw new Error("Endereço inválido.");
  const slug = u.hostname.replace(/^www\./, "").replace(/[^a-z0-9]+/gi, "-").toLowerCase().replace(/^-|-$/g, "").slice(0, 40);
  const nome = (f.nome || u.hostname).replace(/[\r\n]/g, " ").slice(0, 80);
  const cfgl = `{url: ${JSON.stringify(u.href)}, cidade: "São Paulo"${f.lista ? `, listagem: true, padrao_link: ${JSON.stringify(f.padrao || "^/")}, limite: 40, pausa: 2` : ""}}`;
  return { slug, texto: `\n  - slug: ${slug}\n    nome: ${JSON.stringify(nome)}\n    conector: jsonld\n    ativo: true\n    intervalo_horas: 24\n    prioridade: 40\n    autorizacao: autorizada       # adicionado pelo painel do celular\n    config: ${cfgl}\n` };
}
async function adicionarFonte(f) {
  if (!exigirToken()) return;
  if (!f.ok) return aviso("Marque que pode coletar deste site.");
  let t; try { t = trechoFonte(f); } catch (e) { return aviso(e.message || "Endereço inválido."); }
  const g = await gh(`/repos/${cfg.repo}/contents/fontes_eventos.yml?ref=${cfg.dados}`);
  if (!g.ok) return aviso(`Não consegui ler o cadastro (${g.status}).`);
  const arq = await g.json();
  const atual = new TextDecoder().decode(Uint8Array.from(atob(arq.content.replace(/\n/g, "")), (c) => c.charCodeAt(0)));
  if (new RegExp(`^\\s*- slug: ${t.slug}\\s*$`, "m").test(atual)) return aviso("Essa fonte já existe.");
  const novo = (atual.endsWith("\n") ? atual : atual + "\n") + t.texto;
  const bytes = new TextEncoder().encode(novo); let bin = ""; bytes.forEach((b) => { bin += String.fromCharCode(b); });
  const r = await gh(`/repos/${cfg.repo}/contents/fontes_eventos.yml`, { method: "PUT", body: JSON.stringify({ message: `fonte de eventos adicionada pelo painel: ${t.slug}`, content: btoa(bin), sha: arq.sha, branch: cfg.dados }) });
  aviso(r.ok ? "Fonte adicionada. Ela entra na próxima coleta de eventos." : `Não consegui gravar (${r.status}).`);
}

/* ---------- rotas ---------- */
const rota = () => { const p = location.hash.replace(/^#\/?/, "").split("/"); return { tela: p[0] || "inicio", id: p[1] }; };
function desenhar() {
  const r = rota();
  document.querySelectorAll(".abas a").forEach((a) => a.setAttribute("aria-current", a.dataset.tela === (r.tela === "bot" ? "inicio" : r.tela) ? "page" : "false"));
  const caixa = document.getElementById("log-caixa"), colado = caixa && caixa.scrollTop + caixa.clientHeight >= caixa.scrollHeight - 8;
  const y = window.scrollY;
  const tela = r.tela === "bot" ? detalhe(r.id) : r.tela === "dados" ? telaDados() : r.tela === "ajustes" ? telaAjustes() : telaInicio();
  $main.replaceChildren(tela);
  const nova = document.getElementById("log-caixa"); if (nova && colado !== false) nova.scrollTop = nova.scrollHeight;
  window.scrollTo(0, y);
  document.getElementById("titulo").textContent = r.tela === "bot" ? (REG.bots.find((b) => b.id === r.id) || {}).nome || "Bot" : r.tela === "dados" ? "Dados" : r.tela === "ajustes" ? "Ajustes" : "Central de bots";
}
window.addEventListener("hashchange", () => { window.scrollTo(0, 0); desenhar(); if (rota().tela !== "ajustes") atualizar(); });
document.getElementById("btn-atualizar").addEventListener("click", () => atualizar(true));
document.addEventListener("visibilitychange", () => { if (!document.hidden) atualizar(); });
setInterval(() => { if (!document.hidden && Date.now() - ultimaBusca >= (algumRodando() || rota().tela === "bot" ? 8000 : 45000)) atualizar(); }, 4000);

if ("serviceWorker" in navigator && location.protocol.startsWith("http")) navigator.serviceWorker.register("sw.js").catch(() => {});
$main.replaceChildren(h("p", { class: "carregando", text: "Carregando os bots…" }));
atualizar();
window.__painel = { ST, desenhar };   // usado nos testes
})();
