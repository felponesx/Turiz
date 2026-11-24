/* TURIZ Bot Control — painel mobile-first. Sem frameworks; todo texto de fora entra por textContent (sem innerHTML).
   Lê: status/<bot>.json (branch bot-status) e control/*.json (branch bot-control). Comanda o Core disparando o workflow nucleo.yml com um comando em JSON
   (o Core valida tudo; o painel nunca escreve nos arquivos de controle). */
(() => {
"use strict";
const REG = window.BOTS_REGISTRY || { grupos: [], bots: [] };
const PARAMS = new URLSearchParams(location.search);
const PADRAO = { repo: "felponesx/Turiz", branch: "bot-status", ctl: "bot-control", dados: "main", token: "" };
const $main = document.getElementById("main");
const STALE_MIN = 20;
const TZ = "America/Sao_Paulo";

/* ---------- utilidades ---------- */
const lerCfg = () => { try { return { ...PADRAO, ...JSON.parse(localStorage.getItem("turiz-painel") || "{}") }; } catch { return { ...PADRAO }; } };
const salvarCfg = (c) => { try { localStorage.setItem("turiz-painel", JSON.stringify(c)); } catch { /* sem armazenamento */ } };
let cfg = lerCfg();
if (PARAMS.get("repo")) cfg.repo = PARAMS.get("repo");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k === "value") el.value = v;
    else if (k === "checked") el.checked = !!v;
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
  back: '<path d="M15 5l-7 7 7 7"/>', play: '<path d="M8 5l11 7-11 7z"/>', stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  pause: '<path d="M8 5v14M16 5v14"/>', ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v5H5V6h5"/>', next: '<path d="M9 5l7 7-7 7"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>', check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>',
};
function icone(nome) { const s = document.createElementNS("http://www.w3.org/2000/svg", "svg"); s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("class", "i"); s.setAttribute("aria-hidden", "true"); s.innerHTML = ICONES[nome] || ICONES.globe; return s; }
const num = (n) => (n == null || isNaN(n)) ? "—" : Number(n).toLocaleString("pt-BR");
const FMT = new Intl.DateTimeFormat("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const FMT_DIA = new Intl.DateTimeFormat("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit" });
const chaveDia = (d) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(d);
const dh = (iso) => { try { return iso ? FMT.format(new Date(iso)).replace(",", "") : "—"; } catch { return "—"; } };
const hora = (iso) => { try { return new Date(iso).toLocaleTimeString("pt-BR", { timeZone: TZ, hour: "2-digit", minute: "2-digit", second: "2-digit" }); } catch { return ""; } };
function quando(iso) {
  if (!iso) return "nunca";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < -60) return "em " + (s > -3600 ? Math.round(-s / 60) + " min" : s > -86400 ? Math.round(-s / 3600) + " h" : Math.round(-s / 86400) + " d");
  if (s < 45) return "agora"; if (s < 3600) return `há ${Math.round(s / 60)} min`;
  if (s < 86400) return `há ${Math.round(s / 3600)} h`; return `há ${Math.round(s / 86400)} d`;
}
const duracao = (s) => s == null ? "—" : s < 90 ? `${s}s` : s < 5400 ? `${Math.round(s / 60)} min` : `${(s / 3600).toFixed(1)} h`.replace(".", ",");
const seguro = (u) => (typeof u === "string" && /^https:\/\/[^\s"'<>]+$/.test(u)) ? u : null;
let avisoTimer;
function aviso(txt) { const a = document.getElementById("aviso"); a.textContent = txt; a.classList.add("on"); clearTimeout(avisoTimer); avisoTimer = setTimeout(() => a.classList.remove("on"), 5200); }

/* ---------- dados ---------- */
const ROTULO = { pausado: "Pausado", externo: "Automático", rodando: "Rodando", concluido: "Concluído", avisos: "Concluído com avisos", erro: "Erro", aguardando_credencial: "Aguardando chave", aguardando_config: "Aguardando ajuste", semsinal: "Sem sinal", nunca: "Ainda não rodou", ocioso: "Parado" };
const ST = {};                                        // id -> status do bot (ou null)
let REV = null;                                       // resumo do Review (data/revisao_resumo.json), ou null
const CTL = { bots: null, fila: null, resumo: null, config: null };
let redeErro = false, ultimaBusca = 0, buscando = false, ctlOk = false;

async function lerJson(branch, caminho, base) {
  let url, init = { cache: "no-store" };
  if (base) url = base + caminho.split("/").pop();
  else if (cfg.token) { url = `https://api.github.com/repos/${cfg.repo}/contents/${caminho}?ref=${branch}`; init.headers = { Authorization: `Bearer ${cfg.token}`, Accept: "application/vnd.github.raw+json" }; }
  else url = `https://raw.githubusercontent.com/${cfg.repo}/${branch}/${caminho}?t=${Date.now()}`;
  const r = await fetch(url, init);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}
const meta = (id) => REG.bots.find((b) => b.id === id) || { id, nome: id, descricao: "", grupo: "", icone: "globe", agenda: "", requer: [], saidas: [] };
const ctlBot = (id) => ((CTL.bots && CTL.bots.bots) || []).find((b) => b.id === id) || null;
const conf = (id) => (ctlBot(id) || {}).config || { ativo: true, gerenciado: false, prioridade: "normal", agenda: { tipo: "manual" }, depende_de: [], max_tentativas: 3, limites: { max_minutos: 180, lote: null }, categorias: [], reprocessar: "ignorar_existentes" };
const global = () => (CTL.config && CTL.config.global) || (CTL.resumo && CTL.resumo.global) || { pausado: false, max_concorrencia: 1 };
const tarefas = () => (CTL.fila && CTL.fila.tarefas) || [];
const dlq = () => (CTL.fila && CTL.fila.dlq) || [];

function efetivo(s) {
  if (!s) return "nunca";
  if (s.estado === "rodando" && s.atualizado_em && (Date.now() - new Date(s.atualizado_em).getTime()) / 60000 > STALE_MIN) return "semsinal";
  return s.estado || "ocioso";
}
async function atualizar(manual) {
  if (buscando) return; buscando = true;
  const btn = document.getElementById("btn-atualizar"); btn.classList.add("gira");
  let falhas = 0;
  await Promise.all(REG.bots.map(async (b) => {
    try {
      ST[b.id] = await lerJson(cfg.branch, `status/${b.id}.json`, PARAMS.get("base"));
      if (!ST[b.id] && b.externo) ST[b.id] = { estado: "externo", percentual: 0, mensagem: "Roda sozinho todo dia às 11:07 (Brasília) e avisa por notificação no celular." };
    } catch { falhas++; }
  }));
  try { REV = await lerJson(cfg.dados, "data/revisao_resumo.json", PARAMS.get("base")); } catch { /* ainda não gerado */ }
  const ctlBase = PARAMS.get("ctl");
  try {
    const [bots, fila, resumo, config] = await Promise.all(["bots", "fila", "resumo", "config"].map((n) => lerJson(cfg.ctl, `control/${n}.json`, ctlBase)));
    Object.assign(CTL, { bots, fila, resumo, config }); ctlOk = !!(bots || fila || resumo);
  } catch { /* Core indisponível: o painel segue só com os status */ }
  redeErro = falhas === REG.bots.length; ultimaBusca = Date.now(); buscando = false;
  btn.classList.remove("gira");
  if (manual && redeErro) aviso("Sem conexão com o GitHub. Mostrando o último estado conhecido.");
  if (!["ajustes", "config"].includes(rota().tela) && !document.activeElement?.closest?.("form")) desenhar();
}
const algumRodando = () => REG.bots.some((b) => efetivo(ST[b.id]) === "rodando") || tarefas().some((t) => t.estado === "executando");

/* ---------- ações (precisam do token; o Core valida) ---------- */
async function gh(caminho, opcoes = {}) {
  return fetch(`https://api.github.com${caminho}`, { ...opcoes, headers: { Authorization: `Bearer ${cfg.token}`, Accept: "application/vnd.github+json", ...(opcoes.headers || {}) } });
}
function exigirToken() { if (cfg.token) return true; aviso("Para comandar os bots, cole o token do GitHub em Ajustes."); location.hash = "#/ajustes"; return false; }
async function comando(obj, opts = {}) {
  if (opts.confirmar && !window.confirm(opts.confirmar)) return false;
  if (!exigirToken()) return false;
  const t0 = Date.now();
  const r = await gh(`/repos/${cfg.repo}/actions/workflows/nucleo.yml/dispatches`, { method: "POST", body: JSON.stringify({ ref: cfg.dados, inputs: { comando: JSON.stringify(obj) } }) });
  if (r.status !== 204) { aviso(r.status === 403 || r.status === 404 ? "O token não tem permissão de Actions (leitura e escrita)." : `GitHub respondeu ${r.status}`); return false; }
  aviso("Comando enviado. O Core aplica em cerca de 1 minuto.");
  aguardarResultado(t0);
  return true;
}
async function aguardarResultado(t0) {
  for (let i = 0; i < 22; i++) {
    await sleep(7000);
    try {
      const f = await lerJson(cfg.ctl, "control/fila.json", PARAMS.get("ctl"));
      const uc = f && f.meta && f.meta.ultimo_comando;
      if (uc && new Date(uc.em).getTime() >= t0 - 10000) { aviso((uc.ok ? "✓ " : "✗ ") + uc.mensagem); await atualizar(); return; }
    } catch { /* tenta de novo */ }
  }
  aviso("O Core ainda está aplicando. Atualize em instantes.");
}
async function cancelarLegado(s) {     // execução fora do Core (cron/cadeia): cancela direto no GitHub
  if (!exigirToken() || !window.confirm("Cancelar a execução em andamento?")) return;
  const m = /\/actions\/runs\/(\d+)/.exec(s.run_url || ""); if (!m) return aviso("Não achei a execução para cancelar.");
  const r = await gh(`/repos/${cfg.repo}/actions/runs/${m[1]}/cancel`, { method: "POST" });
  aviso(r.status === 202 ? "Cancelamento pedido." : `Não consegui cancelar (${r.status}).`);
  setTimeout(() => atualizar(), 6000);
}

/* ---------- componentes ---------- */
function barra(pct) { return h("div", { class: "barra", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": 100, "aria-valuenow": pct }, h("i", { style: `width:${Math.max(0, Math.min(100, pct))}%` })); }
const kpi = (rot, v, sub) => h("div", { class: "kpi" }, h("b", { text: typeof v === "number" ? num(v) : v }), h("span", { text: rot }), sub ? h("div", { class: "sub", text: sub }) : null);
const secao = (titulo, ...c) => h("div", { class: "secao" }, titulo ? h("h2", { text: titulo }) : null, ...c);
const chip = (txt, cls = "") => h("span", { class: `chip ${cls}`, text: txt });
const ROT_CONTA = { captados: "Captados", novos: "Novos", atualizados: "Atualizados", falhas: "Falhas", bloqueados: "Bloqueados (robots)", completados: "Completados", consultados: "Consultados", pendentes: "Pendentes",
  baixadas: "Baixadas", ja_existiam: "Já existiam", duplicados: "Duplicados", candidatos: "Candidatos", sites_para_visitar: "Sites a visitar", lugares_para_visitar: "Lugares a visitar", para_processar: "A processar", fotos: "Fotos", rejeitados: "Rejeitados" };
const ROT_TOTAL = { lugares: "Lugares", eventos: "Eventos", imagens: "Imagens", vinculos: "Redes sociais", cardapios: "Cardápios", fotos: "Fotos", fotos_ilustrativas: "Fotos ilustrativas", lugares_receita: "Lugares da Receita",
  com_bairro: "Com bairro", com_cep: "Com CEP", com_rua: "Com rua", confirmados: "Confirmados", lugares_com_imagem: "Lugares com imagem", lugares_com_rede: "Lugares com rede", fontes: "Fontes", temas: "Temas", tamanho_kb: "KB de fotos" };
const bonito = (k) => k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const PRIO = { critica: "Crítica", alta: "Alta", normal: "Normal", baixa: "Baixa" };
const ESTADO_T = { criada: "Criada", aguardando: "Aguardando", programada: "Programada", executando: "Executando", em_revisao: "Em revisão", concluida: "Concluída", concluida_parcial: "Concluída parcialmente", falhou: "Falhou", pausada: "Pausada", cancelada: "Cancelada", expirada: "Expirada" };
const CLS_T = { executando: "run", concluida: "ok", concluida_parcial: "warn", falhou: "err", pausada: "warn", cancelada: "", expirada: "", aguardando: "", programada: "ouro" };

function minis(contagem) {
  const itens = Object.entries(contagem || {}).filter(([, v]) => typeof v === "number" && v > 0).slice(0, 4);
  return itens.length ? h("div", { class: "minis" }, itens.map(([k, v]) => h("span", {}, `${ROT_CONTA[k] || bonito(k)} `, h("b", { text: num(v) })))) : null;
}
function cartao(b) {
  const s = ST[b.id], e = efetivo(s), c = conf(b.id), pct = s ? (s.percentual || 0) : 0, sem = e === "nunca" || e === "externo";
  let linha;
  if (e === "rodando") linha = h("div", { class: "captando" }, h("em", { text: "Captando agora: " }), s.atual || s.etapa || "iniciando…");
  else if (e === "externo") linha = h("div", { class: "captando" }, s.mensagem);
  else if (e === "nunca") linha = h("div", { class: "captando" }, h("em", { text: b.agenda ? `Agenda: ${b.agenda}` : "Ainda não rodou" }));
  else linha = h("div", { class: "captando" }, h("em", { text: `Último resultado ${quando(s.finalizado_em || s.atualizado_em)}${s.mensagem ? " — " : ""}` }), s.mensagem || "");
  const chips = h("div", { class: "linha-chips" }, c.ativo === false ? chip("Desligado", "warn") : null, c.gerenciado ? chip("Core", "ouro") : chip("Horário fixo"), chip(PRIO[c.prioridade] || "Normal"));
  return h("a", { class: `cartao est-${e}`, href: `#/bot/${b.id}`, "aria-label": `${b.nome}: ${ROTULO[e]}, ${pct}%` },
    h("div", { class: "cabeca" }, h("div", { class: "ic" }, icone(b.icone)), h("div", { class: "titulo" }, h("b", { text: b.nome }), h("small", { text: b.fonte })), h("span", { class: "selo", text: ROTULO[e] })),
    sem ? null : barra(pct),
    sem ? null : h("div", { class: "linha-p" }, h("span", {}, s && s.etapa && e === "rodando" ? s.etapa : (s && s.iniciado_em ? `Iniciou ${quando(s.iniciado_em)}` : "")), h("b", { text: pct + "%" })),
    linha, s ? minis(s.contagem) : null, chips);
}
function linhaTarefa(t, acoes = true) {
  const m = meta(t.bot);
  const btns = [];
  if (acoes) {
    if (["aguardando", "programada", "criada"].includes(t.estado)) btns.push(h("button", { class: "btn peq", onclick: () => comando({ acao: "pausar_tarefa", id: t.id }) }, "Pausar"), h("button", { class: "btn peq", onclick: () => comando({ acao: "cancelar_tarefa", id: t.id }, { confirmar: "Cancelar esta tarefa?" }) }, "Cancelar"));
    if (t.estado === "pausada") btns.push(h("button", { class: "btn peq", onclick: () => comando({ acao: "retomar_tarefa", id: t.id }) }, "Retomar"), h("button", { class: "btn peq", onclick: () => comando({ acao: "cancelar_tarefa", id: t.id }, { confirmar: "Cancelar esta tarefa?" }) }, "Cancelar"));
    if (t.estado === "executando") btns.push(h("button", { class: "btn peq", onclick: () => comando({ acao: "cancelar_execucao", id: t.id }, { confirmar: "Cancelar a execução em andamento? O que já foi captado é mantido." }) }, "Cancelar execução"));
    if (t.dlq) btns.push(h("button", { class: "btn peq", onclick: () => comando({ acao: "reprocessar", id: t.id }) }, "Reprocessar"));
  }
  const c = t.contagens || {};
  return h("div", { class: "tarefa" },
    h("div", { class: "topo-t" }, h("div", {}, h("b", { text: m.nome }), h("div", { class: "sub", text: `${(t.tipo || "executar").replace(/_/g, " ")} · origem ${t.origem}` })),
      h("div", { style: "text-align:right" }, chip(ESTADO_T[t.estado] || t.estado, CLS_T[t.estado] || ""), h("div", { style: "margin-top:4px" }, chip(PRIO[t.prioridade] || t.prioridade)))),
    h("div", { class: "meta-t", text: [`criada ${dh(t.criada_em)}`, t.programada_para && t.estado === "programada" ? `roda ${dh(t.programada_para)}` : null, t.duracao_s != null ? `duração ${duracao(t.duracao_s)}` : null, `tentativa ${t.tentativas}/${t.max_tentativas}`,
      c.captados ? `captados ${num(c.captados)}` : null, c.novos ? `novos ${num(c.novos)}` : null].filter(Boolean).join(" · ") }),
    t.erro ? h("div", { class: "meta-t", style: "color:var(--err)", text: t.erro }) : null,
    btns.length ? h("div", { class: "acoes", style: "margin-top:8px" }, btns) : null);
}

/* ---------- telas ---------- */
function historicoGeral() {
  // execuções passadas de todos os bots (status.historico) + tarefas finalizadas do Core, mais recentes primeiro
  const itens = [];
  for (const b of REG.bots) for (const x of ((ST[b.id] || {}).historico || [])) itens.push({ bot: b.id, fim: x.fim, inicio: x.inicio, estado: x.estado, msg: x.mensagem, cont: x.contagem || {}, run_url: x.run_url });
  return itens.filter((x) => x.fim).sort((a, b) => (b.fim > a.fim ? 1 : -1));
}
function telaGeral() {
  const ids = REG.bots.map((b) => b.id), efs = ids.map((i) => efetivo(ST[i]));
  const g = global(), hoje = chaveDia(new Date());
  const cont = (f) => efs.filter(f).length;
  const desligados = ids.filter((i) => conf(i).ativo === false).length;
  const hist = historicoGeral();
  const deHoje = hist.filter((x) => chaveDia(new Date(x.fim)) === hoje);
  const soma = (k) => deHoje.reduce((a, x) => a + (x.cont[k] || 0), 0);
  const ultimo = hist[0] && hist[0].fim;
  const proximas = ((CTL.bots && CTL.bots.bots) || []).map((b) => b.proxima_execucao).filter(Boolean).sort();
  const totEv = (ST.eventos && ST.eventos.totais && ST.eventos.totais.eventos);
  const raiz = h("div", {});
  if (redeErro) raiz.append(h("div", { class: "alerta" }, h("b", { text: "Sem conexão" }), "Não consegui falar com o GitHub agora; o que aparece pode estar desatualizado."));
  if (g.pausado) raiz.append(h("div", { class: "alerta" }, h("b", { text: "Automação pausada" }), "Nenhum bot inicia enquanto a pausa geral estiver ligada. Toque em “Retomar automações” abaixo."));
  if (!ctlOk) raiz.append(h("div", { class: "aviso-caixa", text: "O Core ainda não publicou o estado (agenda e fila). Ele roda a cada 10 minutos; os status dos bots abaixo já são reais." }));
  raiz.append(h("div", { class: "kpis g4" }, kpi("Bots cadastrados", ids.length), kpi("Ativos", ids.length - desligados), kpi("Pausados / desligados", g.pausado ? "todos" : desligados),
    kpi("Executando", cont((e) => e === "rodando")), kpi("Com falha", cont((e) => e === "erro" || e === "semsinal")), kpi("Aguardando", cont((e) => e.startsWith("aguardando"))),
    kpi("Tarefas na fila", (CTL.resumo && CTL.resumo.fila && CTL.resumo.fila.na_fila) ?? 0), kpi("Dead-letter", (CTL.resumo && CTL.resumo.fila && CTL.resumo.fila.dead_letter) ?? 0)));
  raiz.append(secao("Captação de hoje (horário de Brasília)", h("div", { class: "kpis g4" },
    kpi("Captados", soma("captados")), kpi("Registros novos", soma("novos")), kpi("Atualizados", soma("atualizados")), kpi("Duplicados", soma("duplicados"), "eventos"),
    kpi("Aguardando revisão", REV ? REV.aguardando_revisao : "—", REV ? "score abaixo de 75" : "o Revisor ainda não rodou"), kpi("Eventos no sistema", totEv ?? "—"), kpi("Última execução", ultimo ? dh(ultimo) : "—"), kpi("Próxima (Core)", proximas[0] ? dh(proximas[0]) : "—", proximas[0] ? quando(proximas[0]) : "só horários fixos"))));
  const duracaoHoje = deHoje.reduce((a, x) => a + Math.max(0, (new Date(x.fim) - new Date(x.inicio)) / 1000), 0);
  raiz.append(secao("Controles rápidos", h("div", { class: "acoes", style: "margin-top:0" },
    h("button", { class: "btn prim", onclick: () => comando({ acao: "executar_todos" }, { confirmar: "Executar todos os bots ativos, em sequência? Isso leva horas." }) }, icone("play"), "Executar todos"),
    g.pausado ? h("button", { class: "btn", onclick: () => comando({ acao: "retomar_tudo" }) }, icone("play"), "Retomar automações")
      : h("button", { class: "btn", onclick: () => comando({ acao: "pausar_tudo" }, { confirmar: "Pausar TODOS os bots? Os que estão rodando terminam; nenhum novo inicia." }) }, icone("pause"), "Pausar tudo"),
    h("button", { class: "btn", onclick: () => comando({ acao: "cancelar_fila" }, { confirmar: "Cancelar todas as tarefas em espera? As já iniciadas continuam." }) }, icone("stop"), "Cancelar fila"),
    h("button", { class: "btn", onclick: () => comando({ acao: "limpar" }, { confirmar: "Remover tarefas antigas (expiradas, canceladas e concluídas há mais de 14 dias)? Tarefas ativas e dead-letter não são tocadas." }) }, "Limpar antigas"),
    h("button", { class: "btn", onclick: () => atualizar(true) }, icone("refresh"), "Atualizar")),
    h("p", { class: "dica", text: `Tempo de execução hoje: ${duracao(Math.round(duracaoHoje))}. Atualizado ${quando(new Date(ultimaBusca).toISOString())}.` })));
  // evolução: execuções reais dos últimos dias (somatório do que cada bot registrou)
  const dias = {};
  for (const x of hist) { const d = chaveDia(new Date(x.fim)); dias[d] = (dias[d] || 0) + (x.cont.novos || 0); }
  const ordenados = Object.entries(dias).sort().slice(-7), max = Math.max(1, ...ordenados.map(([, v]) => v));
  raiz.append(secao("Evolução (registros novos por dia)", ordenados.length
    ? h("div", { class: "barras-dia" }, ordenados.map(([d, v]) => h("div", {}, h("span", { text: FMT_DIA.format(new Date(d + "T12:00:00")) }), h("i", { style: `width:${Math.max(2, (v / max) * 100)}%` }), h("b", { style: "color:var(--ink)", text: num(v) }))))
    : h("div", { class: "lista" }, h("div", { class: "vazio", text: "Ainda sem execuções registradas." })),
    h("p", { class: "dica", text: "Mostra o que os bots registraram nas últimas execuções (até 12 por bot). A série semanal e mensal completa se forma conforme o Core acumula histórico." })));
  raiz.append(secao("Atividade recente", h("div", { class: "lista" }, hist.slice(0, 8).length ? hist.slice(0, 8).map((x) =>
    h("div", {}, h("span", {}, h("b", { text: meta(x.bot).nome }), h("div", { class: "dica", text: `${ROTULO[x.estado] || x.estado}${x.msg ? " — " + x.msg : ""}` })), h("small", { text: dh(x.fim) }))) : h("div", { class: "vazio", text: "Sem atividade registrada ainda." }))));
  return raiz;
}
function telaBots() {
  const raiz = h("div", {});
  const precisa = REG.bots.filter((b) => ["erro", "aguardando_credencial", "aguardando_config", "semsinal"].includes(efetivo(ST[b.id])));
  if (precisa.length) raiz.append(secao("Precisa de você", precisa.map((b) => { const s = ST[b.id], e = efetivo(s);
    return h("a", { class: "alerta", href: `#/bot/${b.id}`, style: "display:block;text-decoration:none;color:inherit" }, h("b", { text: `${b.nome} — ${ROTULO[e]}` }), (s && s.mensagem) || (e === "semsinal" ? "Parou de dar sinal; talvez tenha sido interrompido." : "")); })));
  for (const gr of REG.grupos) { const bs = REG.bots.filter((b) => b.grupo === gr); if (bs.length) raiz.append(secao(gr, bs.map(cartao))); }
  return raiz;
}

const abertos = new Set();
function detalhes(chave, titulo, conteudo) {
  const d = h("details", {}, h("summary", { text: titulo }), conteudo);
  if (abertos.has(chave)) d.open = true;
  d.addEventListener("toggle", () => { d.open ? abertos.add(chave) : abertos.delete(chave); });
  return d;
}
function detalheBot(id) {
  const b = REG.bots.find((x) => x.id === id);
  if (!b) return h("p", { class: "vazio", text: "Bot não encontrado." });
  const s = ST[id], e = efetivo(s), pct = s ? (s.percentual || 0) : 0, c = conf(id), cb = ctlBot(id), est = (cb && cb.estatisticas) || null, sem = e === "nunca" || e === "externo";
  const raiz = h("div", { class: `est-${e}` });
  raiz.append(h("a", { class: "voltar", href: "#/bots" }, icone("back"), "Todos os bots"));
  raiz.append(h("div", { class: "cabeca", style: "margin:6px 0 4px" }, h("div", { class: "ic" }, icone(b.icone)), h("div", { class: "titulo" }, h("h1", { style: "font-size:1.3rem", text: b.nome }), h("small", { text: `${b.fonte} · ${b.id}` })), h("span", { class: "selo", text: ROTULO[e] })));
  raiz.append(h("p", { class: "desc", text: b.descricao }));
  raiz.append(h("div", { class: "cartao", style: "cursor:default" },
    h("div", { class: "linha-p" }, h("span", { text: e === "nunca" ? "Ainda não rodou" : e === "externo" ? "Automático" : (s.etapa || "Progresso") }), h("span", { class: "grande", text: sem ? "–" : pct + "%" })),
    sem ? null : barra(pct),
    e === "rodando" ? h("div", { class: "captando" }, h("em", { text: "Captando agora: " }), s.atual || "iniciando…") : null,
    s && s.total ? h("div", { class: "linha-p" }, h("span", { text: "Itens" }), h("b", { text: `${num(s.feitos)} de ${num(s.total)}` })) : null,
    s ? h("div", { class: "linha-p" }, h("span", { text: "Última atualização" }), h("b", { text: quando(s.atualizado_em) })) : null,
    s && s.mensagem ? h("p", { class: "desc", style: "margin-bottom:0", text: s.mensagem }) : null));
  const botoes = h("div", { class: "acoes" });
  if (b.workflow) botoes.append(h("button", { class: "btn prim", onclick: () => comando({ acao: "enfileirar", bot: id, prioridade: "alta" }) }, icone("play"), "Executar agora"));
  botoes.append(h("button", { class: "btn", onclick: () => comando({ acao: "config_bot", bot: id, campos: { ativo: c.ativo === false } }, { confirmar: c.ativo === false ? null : "Desligar este bot? Ele não inicia mais (nem pelo horário fixo) até você ligar de novo." }) }, icone("pause"), c.ativo === false ? "Ligar bot" : "Pausar bot"));
  if (b.workflow) botoes.append(h("button", { class: "btn", onclick: () => comando({ acao: "reiniciar_bot", bot: id }, { confirmar: "Reiniciar? As tarefas em espera deste bot são canceladas e uma nova é criada com prioridade alta." }) }, "Reiniciar"));
  const exec = tarefas().find((t) => t.bot === id && t.estado === "executando");
  if (e === "rodando") botoes.append(h("button", { class: "btn", onclick: () => exec ? comando({ acao: "cancelar_execucao", id: exec.id }, { confirmar: "Cancelar a execução em andamento?" }) : cancelarLegado(s) }, icone("stop"), "Cancelar execução"));
  const link = s && seguro(s.run_url); if (link) botoes.append(h("a", { class: "btn", href: link, target: "_blank", rel: "noopener" }, icone("ext"), "Ver no GitHub"));
  raiz.append(botoes);
  raiz.append(h("div", { class: "linha-chips" }, c.ativo === false ? chip("Desligado", "warn") : chip("Ativo", "ok"), c.gerenciado ? chip("Agendado pelo Core", "ouro") : chip("Horário fixo: " + (b.agenda || "—")), chip("Prioridade " + (PRIO[c.prioridade] || "normal")),
    cb && cb.proxima_execucao ? chip("Próxima " + dh(cb.proxima_execucao)) : null, b.requer.length ? chip("Precisa de " + b.requer.join(", "), "warn") : null));
  raiz.append(secao("Estatísticas", h("div", { class: "grade" },
    kpi("Execuções (Core)", est ? est.execucoes : 0), kpi("Com sucesso", est ? est.sucessos : 0), kpi("Falhas", est ? est.falhas : 0), kpi("Duração média", est ? duracao(est.duracao_media_s) : "—"),
    ...Object.entries((est && est.contagens) || {}).filter(([, v]) => v).map(([k, v]) => kpi((ROT_CONTA[k] || bonito(k)) + " (total)", v)))));
  if (s && s.contagem && Object.keys(s.contagem).length) raiz.append(secao("Última execução — quantos captou", h("div", { class: "grade" }, Object.entries(s.contagem).map(([k, v]) => kpi(ROT_CONTA[k] || bonito(k), v)))));
  if (s && s.totais && Object.keys(s.totais).length) raiz.append(secao("Total no sistema Turiz", h("div", { class: "grade" }, Object.entries(s.totais).map(([k, v]) => kpi(ROT_TOTAL[k] || bonito(k), v)))));
  if (s && s.fontes && s.fontes.length) raiz.append(secao(`Fontes (${s.fontes.length})`, h("div", { class: "lista" }, s.fontes.map((f) =>
    h("div", {}, h("span", {}, h("b", { text: f.nome }), f.mensagem ? h("div", { class: "dica", text: f.mensagem }) : null, f.novos != null ? h("div", { class: "dica", text: `${num(f.coletados)} coletados · ${num(f.novos)} novos` }) : null), h("small", { text: f.estado }))))));
  raiz.append(secao("O que está sendo captado", s && s.itens && s.itens.length
    ? h("div", { class: "lista" }, s.itens.slice(0, 20).map((i) => h("div", {}, h("span", { text: i.txt }), h("small", { text: hora(i.t) }))))
    : h("div", { class: "lista" }, h("div", { class: "vazio", text: e === "nunca" ? "Quando o bot rodar, o que ele captar aparece aqui em tempo real." : "Nada novo nesta execução." }))));
  const minhas = tarefas().filter((t) => t.bot === id).slice(-6).reverse().concat(dlq().filter((t) => t.bot === id).map((t) => ({ ...t, dlq: true })));
  if (minhas.length) raiz.append(secao("Tarefas deste bot (Core)", minhas.map((t) => linhaTarefa(t))));
  if (s && s.avisos && s.avisos.length) raiz.append(secao("Avisos", h("div", { class: "lista" }, s.avisos.map((a) => h("div", {}, h("span", { text: a }))))));
  raiz.append(detalhes("cfg", "Configuração do bot", formConfig(id)));
  if (s && s.log && s.log.length) raiz.append(detalhes("log", "Registro (log)", h("div", { class: "log", id: "log-caixa", text: s.log.map((l) => `${hora(l.t)}  ${l.txt}`).join("\n") })));
  if (s && s.historico && s.historico.length) raiz.append(detalhes("hist", `Últimas execuções (${s.historico.length})`, h("div", { class: "lista", style: "margin-bottom:12px" }, s.historico.map((x) => {
    const l = seguro(x.run_url); return h("div", {}, h("span", {}, h("b", { text: ROTULO[x.estado] || x.estado }), h("div", { class: "dica", text: (x.mensagem || "") + (x.contagem && x.contagem.novos ? ` · ${x.contagem.novos} novos` : "") })), l ? h("a", { href: l, target: "_blank", rel: "noopener", text: quando(x.fim) }) : h("small", { text: quando(x.fim) }));
  }))));
  return raiz;
}

/* ---------- configuração persistente por bot ---------- */
const DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"];
function formConfig(id) {
  const c = conf(id), m = meta(id), ag = c.agenda || { tipo: "manual" };
  const f = (nome, el) => h("div", {}, h("label", { text: nome }), el);
  const ativo = h("input", { type: "checkbox", checked: c.ativo !== false }), ger = h("input", { type: "checkbox", checked: !!c.gerenciado });
  const prio = h("select", {}, ...["critica", "alta", "normal", "baixa"].map((p) => h("option", { value: p, text: PRIO[p], ...(p === (c.prioridade || "normal") ? { selected: true } : {}) })));
  const tipo = h("select", {}, ...[["manual", "Só manual"], ["intervalo", "A cada N minutos"], ["diaria", "Todo dia"], ["semanal", "Dias da semana"], ["apos", "Depois de outro bot"]].map(([v, t]) => h("option", { value: v, text: t, ...(v === ag.tipo ? { selected: true } : {}) })));
  const minutos = h("input", { type: "number", min: 5, max: 43200, value: ag.minutos || 360 });
  const horas = h("input", { value: (ag.horas || ["06:00"]).join(", "), placeholder: "06:00, 18:30", autocapitalize: "none" });
  const dias = DIAS.map((d, i) => h("label", {}, h("input", { type: "checkbox", value: i, checked: (ag.dias || [0]).includes(i) }), d));
  const apos = REG.bots.filter((b) => b.id !== id).map((b) => h("label", {}, h("input", { type: "checkbox", value: b.id, checked: (ag.bots || []).includes(b.id) }), b.nome));
  const gMin = f("Intervalo (minutos)", minutos), gHoras = f("Horários (Brasília, HH:MM separados por vírgula)", horas), gDias = f("Dias da semana", h("div", { class: "dias" }, dias)), gApos = f("Depois de", h("div", { class: "dias" }, apos));
  const mostrar = () => { const t = tipo.value; gMin.hidden = t !== "intervalo"; gHoras.hidden = !["diaria", "semanal"].includes(t); gDias.hidden = t !== "semanal"; gApos.hidden = t !== "apos"; aviso_.hidden = !(t !== "manual" && !ger.checked && m.agenda); };
  const aviso_ = h("div", { class: "aviso-caixa", text: "Este bot já roda por horário fixo (cron/cadeia). Para esta agenda valer, ligue “Agendado pelo Core”; mas então ele pode rodar duas vezes até você retirar o horário fixo antigo. Sem ligar, vale o horário fixo atual." });
  tipo.addEventListener("change", mostrar); ger.addEventListener("change", mostrar);
  const prioridade = prio, maxT = h("input", { type: "number", min: 1, max: 10, value: c.max_tentativas || 3 });
  const maxMin = h("input", { type: "number", min: 5, max: 720, value: (c.limites || {}).max_minutos || 180 }), lote = h("input", { type: "number", min: 1, value: (c.limites || {}).lote ?? "", placeholder: "sem limite" });
  const regiao = h("input", { value: c.regiao || "", placeholder: "ex.: Pinheiros (opcional)" }), cats = h("input", { value: (c.categorias || []).join(", "), placeholder: "pizza, bar (opcional)" });
  const repro = h("select", {}, ...[["ignorar_existentes", "Ignorar o que já existe"], ["atualizar_existentes", "Atualizar o que já existe"], ["tudo", "Reprocessar tudo"]].map(([v, t]) => h("option", { value: v, text: t, ...(v === (c.reprocessar || "ignorar_existentes") ? { selected: true } : {}) })));
  const form = h("form", { class: "form-bot", onsubmit: (ev) => {
    ev.preventDefault();
    let agenda = { tipo: tipo.value };
    if (agenda.tipo === "intervalo") agenda.minutos = parseInt(minutos.value, 10);
    if (["diaria", "semanal"].includes(agenda.tipo)) agenda.horas = horas.value.split(",").map((x) => x.trim()).filter(Boolean);
    if (agenda.tipo === "semanal") agenda.dias = dias.filter((l) => l.firstChild.checked).map((l) => +l.firstChild.value);
    if (agenda.tipo === "apos") agenda.bots = apos.filter((l) => l.firstChild.checked).map((l) => l.firstChild.value);
    comando({ acao: "config_bot", bot: id, campos: { ativo: ativo.checked, gerenciado: ger.checked, prioridade: prio.value, agenda, max_tentativas: parseInt(maxT.value, 10) || 3,
      limites: { max_minutos: parseInt(maxMin.value, 10) || 180, lote: lote.value ? parseInt(lote.value, 10) : null }, regiao: regiao.value.trim() || null,
      categorias: cats.value.split(",").map((x) => x.trim()).filter(Boolean), reprocessar: repro.value } }, { confirmar: "Salvar esta configuração? Ela passa a valer nos próximos ciclos do Core." });
  } },
    h("div", { class: "interruptor" }, h("span", { text: "Bot ligado" }), ativo), h("div", { class: "interruptor" }, h("span", { text: "Agendado pelo Core" }), ger),
    f("Prioridade", prio), f("Agenda", tipo), gMin, gHoras, gDias, gApos, aviso_,
    f("Tentativas antes de ir para a dead-letter", maxT), f("Tempo máximo por execução (min)", maxMin), f("Tamanho do lote", lote), f("Região", regiao), f("Categorias", cats), f("Reprocessamento", repro),
    h("div", { class: "acoes" }, h("button", { class: "btn prim", type: "submit" }, "Salvar configuração")),
    h("p", { class: "dica", text: "As configurações ficam guardadas no Core (persistentes). Região, categorias e lote passam a ser usados pelos bots de descoberta das próximas fases." }));
  mostrar();
  return form;
}

/* ---------- agenda / fila / mais ---------- */
function telaAgenda() {
  const agora = Date.now(), linhas = REG.bots.map((b) => ({ b, c: conf(b.id), cb: ctlBot(b.id) }));
  const raiz = h("div", {}, h("p", { class: "sub", text: "Horários em Brasília (America/Sao_Paulo). Bots “Core” seguem a agenda editável; os demais seguem o horário fixo dos workflows." }));
  const prox = linhas.filter((l) => l.c.gerenciado && l.cb && l.cb.proxima_execucao).sort((a, b) => (a.cb.proxima_execucao > b.cb.proxima_execucao ? 1 : -1));
  const conflitos = new Set();
  for (let i = 1; i < prox.length; i++) if (new Date(prox[i].cb.proxima_execucao) - new Date(prox[i - 1].cb.proxima_execucao) < 10 * 60000) { conflitos.add(prox[i].b.id); conflitos.add(prox[i - 1].b.id); }
  raiz.append(secao("Agenda dos bots", linhas.map(({ b, c, cb }) => {
    const e = efetivo(ST[b.id]), atrasada = c.gerenciado && cb && cb.proxima_execucao && new Date(cb.proxima_execucao).getTime() < agora - 15 * 60000;
    const espera = (c.depende_de || []).length ? `aguarda ${(c.depende_de || []).map((i) => meta(i).nome).join(", ")}` : (c.agenda && c.agenda.tipo === "apos" ? `depois de ${(c.agenda.bots || []).map((i) => meta(i).nome).join(", ")}` : null);
    return h("a", { class: "tarefa", href: `#/bot/${b.id}`, style: "display:block;text-decoration:none;color:inherit" },
      h("div", { class: "topo-t" }, h("div", {}, h("b", { text: b.nome }), h("div", { class: "sub", text: c.gerenciado ? (cb ? cb.agenda_texto : "—") : `Horário fixo: ${b.agenda || "—"}` })), chip(ROTULO[e] || e, e === "rodando" ? "run" : e === "erro" ? "err" : "")),
      h("div", { class: "linha-chips" }, c.ativo === false ? chip("Desligado", "warn") : null, c.gerenciado ? chip("Core", "ouro") : chip("Horário fixo"), cb && cb.proxima_execucao ? chip("Próxima " + dh(cb.proxima_execucao) + " (" + quando(cb.proxima_execucao) + ")") : null,
        cb && cb.estatisticas && cb.estatisticas.duracao_media_s ? chip("~" + duracao(cb.estatisticas.duracao_media_s)) : null, conflitos.has(b.id) ? chip("Conflito de horário", "warn") : null, atrasada ? chip("Atrasada", "err") : null, espera ? chip(espera, "warn") : null));
  })));
  raiz.append(h("p", { class: "dica", text: "Toque em um bot para editar horário, dias, intervalo, prioridade e dependências." }));
  return raiz;
}
function telaFila() {
  const filtro = telaFila.filtro || "ativas";
  const ativas = tarefas().filter((t) => ["criada", "aguardando", "programada", "executando", "pausada"].includes(t.estado));
  const fin = tarefas().filter((t) => ["concluida", "concluida_parcial", "cancelada", "expirada", "falhou"].includes(t.estado)).sort((a, b) => ((b.finalizada_em || "") > (a.finalizada_em || "") ? 1 : -1));
  const grupos = { ativas, concluidas: fin.filter((t) => t.estado.startsWith("concluida")), problemas: fin.filter((t) => ["cancelada", "expirada", "falhou"].includes(t.estado)), dlq: dlq().map((t) => ({ ...t, dlq: true })) };
  const raiz = h("div", {});
  const r = CTL.resumo && CTL.resumo.fila;
  raiz.append(h("div", { class: "kpis g4" }, kpi("Na fila", r ? r.na_fila : 0), kpi("Executando", r ? r.executando : 0), kpi("Dead-letter", grupos.dlq.length), kpi("Concorrência máx.", global().max_concorrencia || 1)));
  const filtros = h("div", { class: "filtros", role: "group", "aria-label": "Filtrar tarefas" }, ...[["ativas", "Ativas"], ["concluidas", "Concluídas"], ["problemas", "Canceladas/expiradas"], ["dlq", "Dead-letter"]].map(([k, t]) =>
    h("button", { "aria-pressed": String(filtro === k), onclick: () => { telaFila.filtro = k; desenhar(); } }, `${t} (${grupos[k].length})`)));
  raiz.append(h("div", { style: "margin-top:16px" }, filtros));
  const lista = grupos[filtro];
  raiz.append(...(lista.length ? lista.slice(0, 60).map((t) => linhaTarefa(t)) : [h("div", { class: "lista" }, h("div", { class: "vazio", text: filtro === "dlq" ? "Nenhuma tarefa na dead-letter queue." : "Nenhuma tarefa aqui." }))]));
  raiz.append(h("div", { class: "acoes" }, h("button", { class: "btn", onclick: () => comando({ acao: "cancelar_fila" }, { confirmar: "Cancelar todas as tarefas em espera?" }) }, icone("stop"), "Cancelar fila"), h("button", { class: "btn", onclick: () => comando({ acao: "limpar" }, { confirmar: "Remover tarefas antigas?" }) }, "Limpar antigas")));
  raiz.append(h("p", { class: "dica", text: "A fila é compartilhada: uma tarefa por bot por vez, prioridade crítica > alta > normal > baixa. Falhas são tentadas de novo com espera crescente (backoff com variação) e, esgotadas as tentativas, vão para a dead-letter, de onde você pode reprocessar." }));
  return raiz;
}
function telaMais() {
  const item = (href, titulo, sub, extra) => h("a", { href, class: extra || "" }, h("span", {}, titulo, h("br"), h("small", { text: sub })), icone("next"));
  return h("div", { class: "menu-mais" },
    item("#/dados", "Banco de dados", "O que cada bot já guardou no sistema Turiz"), item("#/eventos", "Eventos", "Eventos captados, fontes e situação"),
    item("#/historico", "Histórico", "Execuções passadas de todos os bots"), item("#/logs", "Logs", "Registro de cada bot"), item("#/fontes", "Fontes", "Fontes de eventos e adicionar sites"),
    item("#/custos", "Custos e consumo", "Tempo de execução e limites medidos"), item("#/ajustes", "Configurações", "Conexão, token e regras gerais do Core"),
    item("#/em-breve/descobertas", "Descobertas", "Perfis e lugares novos — próxima fase", "em-breve"), item("#/cobertura", "Cobertura geográfica", COB.resumo ? `${COB.resumo.distritos_mapeados} distritos · score médio ${String(COB.resumo.score_medio).replace(".", ",")}` : "Mapa, lacunas e prioridades de coleta"), item("#/revisao", "Revisão", REV ? `${num(REV.aguardando_revisao)} lugares para revisar · score médio ${String(REV.medias.confiabilidade).replace(".", ",")}` : "Score, duplicados e localização"));
}
const FAIXA_ROT = { alta: "Alta (90–100)", confiavel: "Confiável (75–89)", necessita_revisao: "Necessita revisão (50–74)", baixa_confianca: "Baixa confiança (25–49)", nao_confirmado: "Não confirmado (0–24)" };
const FLAG_ROT = { coordenadas_invalidas: "Coordenadas inválidas", fora_da_area: "Fora da área de São Paulo", coordenada_aproximada: "Coordenada aproximada", endereco_incompleto: "Sem rua", sem_numero: "Sem número", sem_bairro: "Sem bairro", sem_cep: "Sem CEP", cep_invalido: "CEP inválido", cep_fora_de_sp: "CEP fora de SP capital" };
const DUP_ROT = { duplicado_confirmado: "Duplicados confirmados", possivel_duplicado: "Possíveis duplicados", unidade_diferente: "Unidades diferentes (não unidas)" };
function telaRevisao() {
  const raiz = h("div", {}, h("a", { class: "voltar", href: "#/mais" }, icone("back"), "Mais"), h("h2", { style: "margin:8px 0", text: "Revisão" }));
  if (!REV) return raiz.append(h("div", { class: "aviso-caixa", text: "O Revisor ainda não rodou. Abra Bots → Revisor → Executar agora. Nenhum número aparece antes de haver dados reais." })) || raiz;
  raiz.append(h("div", { class: "kpis g4" }, kpi("Lugares analisados", REV.total), kpi("Publicáveis", REV.publicaveis, "score ≥ " + REV.config.minimo_para_publicar), kpi("Para revisar", REV.aguardando_revisao),
    kpi("Confiabilidade média", String(REV.medias.confiabilidade).replace(".", ","), "de 100"), kpi("Completude média", String(REV.medias.completude).replace(".", ","), "de 100"), kpi("Duplicados ligados", REV.duplicados_relacionados)));
  const max = Math.max(1, ...Object.values(REV.faixas));
  const linhas = (obj, rot) => h("div", { class: "barras-dia" }, Object.entries(obj).sort((a, b) => b[1] - a[1]).map(([k, v]) => h("div", {}, h("span", { text: rot[k] || bonito(k) }), h("i", { style: `width:${Math.max(2, (v / Math.max(1, ...Object.values(obj))) * 100)}%` }), h("b", { style: "color:var(--ink)", text: num(v) }))));
  raiz.append(secao("Confiabilidade (0–100)", linhas(REV.faixas, FAIXA_ROT)));
  raiz.append(secao("Problemas de localização", Object.keys(REV.flags).length ? linhas(REV.flags, FLAG_ROT) : h("div", { class: "vazio", text: "Nenhum problema encontrado." })));
  raiz.append(secao("Duplicidade", Object.keys(REV.duplicidade).length ? linhas(REV.duplicidade, DUP_ROT) : h("div", { class: "vazio", text: "Nenhum par encontrado." })));
  raiz.append(secao("Por fonte", h("div", { class: "lista" }, Object.entries(REV.por_fonte).map(([f, c]) => h("div", { style: "display:block" }, h("b", { text: f }), h("div", { class: "minis" }, Object.entries(c).map(([k, v]) => h("span", {}, `${FAIXA_ROT[k] || k} `, h("b", { text: num(v) }))))))))); 
  raiz.append(h("p", { class: "dica", text: `Gerado em ${dh(REV.gerado_em)}. O score soma: fontes independentes (até ${REV.config.pesos.fontes}), nome (${REV.config.pesos.nome}), localização (${REV.config.pesos.geo}), endereço (${REV.config.pesos.endereco}), foto rastreável (${REV.config.pesos.visual}) e atualidade (${REV.config.pesos.atualidade}). Fontes copiadas entre si contam uma vez só; faltar Instagram, cardápio ou telefone não tira pontos. A lista caso a caso e os botões Aprovar/Rejeitar ainda não existem.` }));
  return raiz;
}

/* ---------- Inteligência → Cobertura geográfica ---------- */
const COB = { carregado: false, carregando: false, erro: null, resumo: null, bairros: null, metricas: null, categorias: null, prioridades: null, historico: null };
const FILTRO_COB = { zona: null, status: null };
const CV_ROT = { muito_boa: "Muito boa", boa: "Boa", moderada: "Moderada", baixa: "Baixa", critica: "Crítica", desconhecida: "Desconhecida" };
const TERR_ROT = { confirmed: "Confirmado", probable: "Provável", approximate: "Aproximado", unknown: "Desconhecido", boundary_conflict: "Perto da divisa" };
const SCANNER_ROT = (s) => s.nome + (s.disponivel ? "" : " (ainda não existe)");
async function lerGz(caminho) {
  const base = PARAMS.get("base"); let url, init = { cache: "no-store" };
  if (base) url = base + caminho.split("/").pop();
  else if (cfg.token) { url = `https://api.github.com/repos/${cfg.repo}/contents/${caminho}?ref=${cfg.dados}`; init.headers = { Authorization: `Bearer ${cfg.token}`, Accept: "application/vnd.github.raw+json" }; }
  else url = `https://raw.githubusercontent.com/${cfg.repo}/${cfg.dados}/${caminho}?t=${Date.now()}`;
  const r = await fetch(url, init);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error("HTTP " + r.status);
  if (typeof DecompressionStream === "undefined") throw new Error("Este navegador não abre arquivos .gz");
  return new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).json();
}
async function carregarCobertura() {
  if (COB.carregando || COB.carregado) return; COB.carregando = true;
  try {
    const [resumo, bairros, metricas, categorias, prioridades, historico] = await Promise.all([lerJson(cfg.dados, "data/coverage_summary.json", PARAMS.get("base")),
      ...["neighborhoods", "metrics", "categories", "priorities", "history"].map((n) => lerGz(`data/coverage_${n}.json.gz`))]);
    Object.assign(COB, { resumo, bairros, metricas, categorias, prioridades, historico, carregado: !!(resumo && bairros && metricas), erro: resumo ? null : "nao-gerado" });
  } catch (e) { COB.erro = String(e.message || e); }
  COB.carregando = false; desenhar();
}
const mCob = (id) => ((COB.metricas && COB.metricas.metricas) || []).find((m) => m.id === id);
const bCob = (id) => ((COB.bairros && COB.bairros.distritos) || []).find((b) => b.id === id);
const rotCat = (c) => ({ eventos: "Eventos gastronômicos" }[c]) || (COB.resumo && (COB.resumo.categorias_rotulos || {})[c]) || bonito(c);
function mapaSvg(onClick) {
  const ds = COB.bairros.distritos, NS = "http://www.w3.org/2000/svg";
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (const d of ds) for (const pol of d.geometry) for (const [x, y] of pol[0]) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
  const k = Math.cos((-23.55 * Math.PI) / 180), K = 1000 / ((x1 - x0) * k), H = (y1 - y0) * K;
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 1000 ${H.toFixed(0)}`); svg.setAttribute("class", "mapa-cv"); svg.setAttribute("role", "group"); svg.setAttribute("aria-label", "Mapa de cobertura dos distritos de São Paulo");
  for (const d of ds) {
    const m = mCob(d.id) || { status: "desconhecida" };
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d", d.geometry.map((pol) => pol.map((anel) => "M" + anel.map(([x, y]) => `${((x - x0) * k * K).toFixed(1)},${((y1 - y) * K).toFixed(1)}`).join("L") + "Z").join("")).join(""));
    p.setAttribute("fill-rule", "evenodd"); p.setAttribute("class", `cv cv-${m.status}` + (FILTRO_COB.zona && d.zone !== FILTRO_COB.zona || FILTRO_COB.status && m.status !== FILTRO_COB.status ? " apagado" : ""));
    p.setAttribute("tabindex", "0"); p.setAttribute("role", "link");
    const rot = `${d.name}, zona ${d.zone}: cobertura ${CV_ROT[m.status].toLowerCase()}` + (m.coverage_score != null ? `, score ${m.coverage_score}` : "");
    p.setAttribute("aria-label", rot);
    const t = document.createElementNS(NS, "title"); t.textContent = rot; p.append(t);
    p.addEventListener("click", () => onClick(d.id)); p.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(d.id); } });
    svg.append(p);
  }
  return svg;
}
function telaCobertura() {
  const raiz = h("div", {}, h("a", { class: "voltar", href: "#/mais" }, icone("back"), "Mais"), h("h2", { style: "margin:8px 0", text: "Cobertura geográfica" }));
  if (!COB.carregado) { carregarCobertura(); return raiz.append(h("div", { class: "aviso-caixa", text: COB.erro === "nao-gerado" ? "A análise de cobertura ainda não foi gerada. Abra Bots → Cobertura geográfica → Executar agora." : COB.erro ? "Não consegui carregar a cobertura: " + COB.erro : "Carregando o mapa e os indicadores…" })) || raiz; }
  const r = COB.resumo, ms = COB.metricas.metricas;
  raiz.append(h("p", { class: "dica", style: "margin-top:0", text: r.situacao }));
  raiz.append(h("div", { class: "kpis g4" }, kpi("Distritos mapeados", r.distritos_mapeados, "fonte oficial da Prefeitura"), kpi("Pesquisados", r.distritos_pesquisados, "nenhuma busca por distrito ainda"), kpi("Score médio", String(r.score_medio).replace(".", ","), "de 100"),
    kpi("Lugares analisados", r.lugares_total), kpi("Confiáveis", r.lugares_confiaveis, "score ≥ 75"), kpi("Aguardando revisão", r.lugares_aguardando_revisao), kpi("Categorias", r.categorias_identificadas), kpi("Bairro confirmado", 0, "sem malha oficial de bairros")));
  const mk = (campo, itens) => h("div", { class: "filtros", role: "group", "aria-label": "Filtro " + campo }, h("button", { "aria-pressed": FILTRO_COB[campo] == null, onclick: () => { FILTRO_COB[campo] = null; desenhar(); } }, "Todos"),
    ...itens.map(([v, t, n]) => h("button", { "aria-pressed": FILTRO_COB[campo] === v, onclick: () => { FILTRO_COB[campo] = FILTRO_COB[campo] === v ? null : v; desenhar(); } }, n != null ? `${t} (${n})` : t)));
  raiz.append(secao("Mapa", mk("status", Object.keys(CV_ROT).map((k) => [k, CV_ROT[k], r.faixas[k] || 0])), mk("zona", ["Centro", "Norte", "Sul", "Leste", "Oeste"].map((z) => [z, z, r.por_zona[z].distritos])), h("div", { class: "mapa-caixa" }, mapaSvg((id) => { location.hash = "#/cobertura/" + id; })),
    h("p", { class: "dica", text: "Toque num distrito para abrir. A cor indica a faixa; o nome da faixa também aparece nos filtros e nas listas." })));
  const linha = (m) => h("a", { class: "linha-cv", href: "#/cobertura/" + m.id }, h("span", {}, h("b", { text: m.nome }), h("small", { text: ` ${m.zona} · ${num(m.lugares)} lugares` })), h("span", { class: `chip cvchip-${m.status}`, text: `${CV_ROT[m.status]} · ${m.score}` }));
  raiz.append(secao("Maiores lacunas de cobertura", h("div", { class: "lista" }, r.maiores_lacunas.map(linha))));
  raiz.append(secao("Mais bem cobertos", h("div", { class: "lista" }, r.melhores.map(linha))));
  raiz.append(secao("Para onde ir primeiro", h("div", { class: "lista" }, r.regioes_para_explorar.map((x) => h("a", { class: "linha-cv", href: "#/cobertura/" + x.id, style: "display:block" }, h("b", { text: `Prioridade ${x.prioridade} — ${x.nome}` }), h("small", { style: "display:block", text: x.motivo }))))));
  raiz.append(secao("Categorias menos encontradas", h("div", { class: "lista" }, r.categorias_menos_encontradas.map((c) => h("div", {}, h("span", { text: c.rotulo }), h("b", { text: num(c.lugares) + " lugares" }))))));
  raiz.append(secao("Scanners sugeridos", h("div", { class: "lista" }, r.scanners_sugeridos.map((s) => h("div", {}, h("span", { text: s.nome }), h("small", { text: s.disponivel ? `${s.distritos} dos 5 distritos prioritários` : `${s.distritos} dos 5 · ainda não construído` }))))));
  if (r.comparacao) raiz.append(secao("Desde o snapshot anterior", h("p", { class: "dica", text: `${r.comparacao.de} → ${r.comparacao.para}: ${r.comparacao.melhoraram.length} distritos melhoraram, ${r.comparacao.pioraram.length} pioraram, ${num(r.comparacao.novos_lugares)} lugares novos.` })));
  else raiz.append(secao("Evolução", h("p", { class: "dica", text: "O histórico começou agora. A comparação aparece a partir do segundo dia de análise." })));
  raiz.append(h("p", { class: "dica", text: "Limites: " + r.limites.join(" ") + ` Dados geográficos: ${r.fonte_geografica}. Gerado em ${dh(r.gerado_em)}.` }));
  return raiz;
}
function detalheCobertura(id) {
  const raiz = h("div", {}, h("a", { class: "voltar", href: "#/cobertura" }, icone("back"), "Cobertura"));
  if (!COB.carregado) { carregarCobertura(); return raiz.append(h("div", { class: "aviso-caixa", text: "Carregando…" })) || raiz; }
  const b = bCob(id), m = mCob(id);
  if (!b || !m) return raiz.append(h("div", { class: "vazio", text: "Distrito não encontrado." })) || raiz;
  const cats = COB.categorias.categorias.filter((c) => c.neighborhood_id === id), pri = COB.prioridades.prioridades.filter((p) => p.neighborhood_id === id);
  const pd = pri.find((p) => p.category == null);
  raiz.append(h("h2", { style: "margin:8px 0 2px", text: b.name }), h("div", { class: "linha-chips" }, chip(`Zona ${b.zone}`), chip(b.subprefecture ? "Subprefeitura " + b.subprefecture : "Subprefeitura —"), h("span", { class: `chip cvchip-${m.status}`, text: `Cobertura ${CV_ROT[m.status].toLowerCase()}${m.coverage_score != null ? " · " + m.coverage_score : ""}` })));
  raiz.append(h("div", { class: "kpis g4", style: "margin-top:10px" }, kpi("Lugares", m.total_places), kpi("Publicáveis", m.publishable_places), kpi("Para revisar", m.review_places), kpi("Baixa confiança", m.low_confidence_places),
    kpi("Localização aproximada", m.approximate_location_places), kpi("Sem bairro confirmado", m.unconfirmed_neighborhood_places, "distrito é o nível oficial"), kpi("Diversidade", String(m.diversity_score).replace(".", ","), `${m.category_count} categorias`), kpi("Prioridade de coleta", pd ? pd.priority_score : "—")));
  if (m.coverage_score == null) raiz.append(h("div", { class: "aviso-caixa", text: "Poucos dados para avaliar. Isso é falta de informação, não ausência de gastronomia." }));
  else raiz.append(secao("Como o score foi composto", h("div", { class: "barras-dia" }, Object.entries(m.componentes).map(([k, v]) => h("div", {}, h("span", { text: ({ densidade: "Densidade", diversidade: "Diversidade", confiabilidade: "Confiabilidade", precisao: "Precisão", experiencias: "Experiências", atualidade: "Atualidade" })[k] }), h("i", { style: `width:${Math.max(2, v * 100)}%` }), h("b", { style: "color:var(--ink)", text: `${Math.round(v * 100)}%` })))), h("p", { class: "dica", text: `Densidade ${String(m.density_per_km2).replace(".", ",")} lugares/km² (meta relativa da cidade ${String(COB.metricas.meta_densidade_por_km2).replace(".", ",")}). Concentração: ${m.dominant_category ? rotCat(m.dominant_category) + ", índice " + String(m.concentration_index).replace(".", ",") : "—"}.` })));
  const presentes = cats.filter((c) => c.place_count > 0).sort((a, c) => c.place_count - a.place_count), falta = cats.filter((c) => c.place_count === 0);
  const maxc = Math.max(1, ...presentes.map((c) => c.place_count));
  raiz.append(secao("Categorias presentes", presentes.length ? h("div", { class: "barras-dia" }, presentes.map((c) => h("div", {}, h("span", { text: rotCat(c.category) }), h("i", { style: `width:${Math.max(2, (c.place_count / maxc) * 100)}%` }), h("b", { style: "color:var(--ink)", text: num(c.place_count) })))) : h("div", { class: "vazio", text: "Nenhuma categoria detectada." })));
  raiz.append(secao("Categorias ausentes", falta.length ? h("div", { class: "linha-chips" }, falta.map((c) => chip(rotCat(c.category)))) : h("div", { class: "vazio", text: "Nenhuma categoria da cidade está ausente aqui." })));
  if (pd) raiz.append(secao("Recomendação de coleta", h("div", { class: "lista" }, h("div", { style: "display:block" }, h("b", { text: `Prioridade ${pd.priority_score}` }), h("small", { style: "display:block", text: pd.priority_reason }), h("small", { style: "display:block", text: "Objetivo: " + pd.objective }), h("small", { style: "display:block", text: "Scanners: " + pd.recommended_scanners.map(SCANNER_ROT).join(", ") })))));
  const lac = pri.filter((p) => p.category).slice(0, 6);
  if (lac.length) raiz.append(secao("Possíveis lacunas por categoria", h("div", { class: "lista" }, lac.map((p) => h("div", { style: "display:block" }, h("b", { text: `${rotCat(p.category)} · ${p.priority_score}` }), h("small", { style: "display:block", text: p.priority_reason }))))));
  const hist = COB.historico.snapshots.filter((s) => s.distritos[id]);
  raiz.append(secao("Histórico", hist.length ? h("div", { class: "lista" }, hist.slice(-8).reverse().map((s) => h("div", {}, h("span", { text: s.snapshot_date }), h("small", { text: `${num(s.distritos[id].total_places)} lugares · cobertura ${s.distritos[id].coverage_score ?? "—"}` })))) : h("div", { class: "vazio", text: "Sem snapshots." }),
    h("p", { class: "dica", text: COB.historico.buscas.filter((x) => x.neighborhood_id === id).length ? "" : "Nenhuma busca por distrito foi feita ainda." })));
  raiz.append(h("div", { class: "acoes" },
    h("button", { class: "btn", onclick: () => comando({ acao: "enfileirar", bot: "cobertura", prioridade: "normal" }) }, icone("refresh"), "Atualizar análise"),
    h("button", { class: "btn", onclick: () => { const blob = new Blob([JSON.stringify({ distrito: { ...b, geometry: undefined }, metricas: m, categorias: cats, prioridades: pri, historico: hist }, null, 1)], { type: "application/json" }); const a = h("a", { href: URL.createObjectURL(blob), download: `cobertura-${id}.json` }); document.body.append(a); a.click(); a.remove(); } }, icone("ext"), "Exportar dados")));
  raiz.append(h("p", { class: "dica", text: "Pesquisar o distrito ou uma categoria só será possível quando existirem scanners que aceitem distrito como alvo; nesta fase a cobertura só recomenda e nada é disparado." }));
  return raiz;
}
function telaEmBreve(nome) {
  const t = { descobertas: ["Descobertas", "Aqui aparecerão os estabelecimentos e perfis novos achados pelos scanners (Instagram, Geo, Web e Social), com a origem e a cobertura por região e categoria."],
  }[nome] || ["Em breve", ""];
  return h("div", {}, h("a", { class: "voltar", href: "#/mais" }, icone("back"), "Mais"), h("h2", { style: "margin:8px 0", text: t[0] }), h("div", { class: "aviso-caixa", text: t[1] + " Esta etapa ainda não foi construída; nenhum número é mostrado até haver dados reais." }));
}
function telaDados() {
  const raiz = h("div", {}, secao("O que cada bot já guardou no sistema", null));
  const lista = h("div", { class: "lista" });
  for (const b of REG.bots) {
    const t = ST[b.id] && ST[b.id].totais;
    if (!t || !Object.keys(t).length) continue;
    lista.append(h("div", { style: "display:block" }, h("b", { text: b.nome }), h("div", { class: "minis" }, Object.entries(t).map(([k, v]) => h("span", {}, `${ROT_TOTAL[k] || bonito(k)} `, h("b", { text: num(v) }))))));
  }
  if (!lista.children.length) lista.append(h("div", { class: "vazio", text: "Os totais aparecem depois da primeira execução de cada bot." }));
  raiz.append(lista);
  const arquivos = REG.bots.flatMap((b) => b.saidas).filter((v, i, a) => a.indexOf(v) === i);
  raiz.append(secao("Arquivos de dados", h("div", { class: "lista" }, arquivos.map((p) => h("div", {}, h("span", { text: p }), h("a", { href: `https://github.com/${cfg.repo}/blob/${cfg.dados}/${p}`, target: "_blank", rel: "noopener", text: "abrir" }))))));
  raiz.append(h("p", { class: "dica", text: "Tudo que os bots captam entra direto no sistema Turiz, sem aprovação. O app Turiz recebe esses dados automaticamente todo dia." }));
  return raiz;
}
function telaEventos() {
  const s = ST.eventos;
  const raiz = h("div", {}, h("a", { class: "voltar", href: "#/mais" }, icone("back"), "Mais"));
  if (!s) return raiz.appendChild(h("div", { class: "aviso-caixa", text: "O bot de eventos ainda não rodou." })) && raiz;
  raiz.append(h("div", { class: "kpis g4" }, kpi("Eventos no sistema", (s.totais || {}).eventos), kpi("Fontes", (s.totais || {}).fontes), kpi("Captados (última)", (s.contagem || {}).captados), kpi("Novos", (s.contagem || {}).novos)));
  raiz.append(secao("Fontes e situação", h("div", { class: "lista" }, (s.fontes || []).map((f) => h("div", {}, h("span", {}, h("b", { text: f.nome }), f.mensagem ? h("div", { class: "dica", text: f.mensagem }) : null, f.novos != null ? h("div", { class: "dica", text: `${num(f.coletados)} coletados · ${num(f.novos)} novos` }) : null), h("small", { text: f.estado }))))));
  raiz.append(h("div", { class: "acoes" }, h("a", { class: "btn", href: "#/bot/eventos" }, "Abrir o bot de eventos")));
  raiz.append(h("p", { class: "dica", text: "Eventos expirados saem das listagens ativas, mas ficam no histórico (nada é apagado)." }));
  return raiz;
}
function telaHistorico() {
  const hist = historicoGeral().slice(0, 60);
  const fin = tarefas().filter((t) => ["concluida", "concluida_parcial", "falhou", "cancelada", "expirada"].includes(t.estado)).sort((a, b) => ((b.finalizada_em || "") > (a.finalizada_em || "") ? 1 : -1)).slice(0, 20);
  return h("div", {}, h("a", { class: "voltar", href: "#/mais" }, icone("back"), "Mais"),
    fin.length ? secao("Tarefas do Core", fin.map((t) => linhaTarefa(t, false))) : null,
    secao("Execuções dos bots", h("div", { class: "lista" }, hist.length ? hist.map((x) => { const l = seguro(x.run_url);
      return h("div", {}, h("span", {}, h("b", { text: meta(x.bot).nome }), h("div", { class: "dica", text: `${ROTULO[x.estado] || x.estado} · ${duracao(Math.max(0, Math.round((new Date(x.fim) - new Date(x.inicio)) / 1000)))}${x.cont.novos ? ` · ${x.cont.novos} novos` : ""}${x.msg ? " — " + x.msg : ""}` })), l ? h("a", { href: l, target: "_blank", rel: "noopener", text: dh(x.fim) }) : h("small", { text: dh(x.fim) })); })
      : h("div", { class: "vazio", text: "Sem execuções registradas." }))));
}
function telaLogs(id) {
  const sel = h("select", { onchange: (e) => { location.hash = `#/logs/${e.target.value}`; } }, ...REG.bots.map((b) => h("option", { value: b.id, text: b.nome, ...(b.id === (id || "osm") ? { selected: true } : {}) })));
  const alvo = id || "osm", s = ST[alvo];
  const t = tarefas().filter((x) => x.bot === alvo).slice(-5).flatMap((x) => (x.logs || []).map((l) => `[tarefa ${x.id}] ${l}`));
  return h("div", {}, h("a", { class: "voltar", href: "#/mais" }, icone("back"), "Mais"), h("label", { text: "Bot" }), sel,
    secao("Registro da última execução", h("div", { class: "log", text: s && s.log && s.log.length ? s.log.map((l) => `${hora(l.t)}  ${l.txt}`).join("\n") : "Sem registro ainda." })),
    t.length ? secao("Registro das tarefas do Core", h("div", { class: "log", text: t.join("\n") })) : null);
}
function telaFontes() {
  const s = ST.eventos;
  return h("div", {}, h("a", { class: "voltar", href: "#/mais" }, icone("back"), "Mais"),
    secao("Fontes de eventos", h("div", { class: "lista" }, s && s.fontes && s.fontes.length ? s.fontes.map((f) => h("div", {}, h("span", {}, h("b", { text: f.nome }), f.mensagem ? h("div", { class: "dica", text: f.mensagem }) : null), h("small", { text: f.estado }))) : h("div", { class: "vazio", text: "Sem fontes registradas ainda." }))),
    h("h2", { style: "margin:24px 0 4px", text: "Adicionar site de eventos" }), formFonte());
}
function telaCustos() {
  const hist = historicoGeral(), por = {};
  for (const x of hist) { const d = Math.max(0, (new Date(x.fim) - new Date(x.inicio)) / 1000); por[x.bot] = por[x.bot] || { n: 0, s: 0 }; por[x.bot].n++; por[x.bot].s += d; }
  const linhas = Object.entries(por).sort((a, b) => b[1].s - a[1].s);
  const total = linhas.reduce((a, [, v]) => a + v.s, 0);
  return h("div", {}, h("a", { class: "voltar", href: "#/mais" }, icone("back"), "Mais"),
    h("div", { class: "kpis g4" }, kpi("Tempo nas últimas execuções", duracao(Math.round(total))), kpi("Execuções registradas", hist.length), kpi("Custo em dinheiro", "R$ 0", "GitHub Actions é grátis em repositório público"), kpi("Chaves pagas", "0", "Google/Ticketmaster aguardando chave")),
    secao("Tempo de execução por bot", h("div", { class: "lista" }, linhas.length ? linhas.map(([id, v]) => h("div", {}, h("span", {}, h("b", { text: meta(id).nome }), h("div", { class: "dica", text: `${v.n} execuções · média ${duracao(Math.round(v.s / v.n))}` })), h("small", { text: duracao(Math.round(v.s)) }))) : h("div", { class: "vazio", text: "Sem execuções registradas." }))),
    h("p", { class: "dica", text: "Mostra o que foi medido de verdade. Consumo de cotas de APIs pagas será medido quando as chaves existirem." }));
}

/* ---------- fontes de eventos: adicionar site (valida e edita fontes_eventos.yml; precisa de Contents: escrita) ---------- */
function formFonte() {
  const url = h("input", { id: "f-url", placeholder: "https://site-de-eventos.com.br/agenda", inputmode: "url", autocapitalize: "none" });
  const nome = h("input", { id: "f-nome", placeholder: "Nome da fonte (ex.: Agenda do Sesc)" });
  const lista = h("input", { id: "f-lista", type: "checkbox" });
  const padrao = h("input", { id: "f-padrao", placeholder: "Padrão dos links, ex.: ^/evento/", autocapitalize: "none" });
  const ok = h("input", { id: "f-ok", type: "checkbox" });
  return h("div", {},
    h("p", { class: "dica", text: "O bot lê os dados estruturados (schema.org) das páginas e respeita o robots.txt do site. Se o site bloquear robôs, a fonte aparece como bloqueada. Para adicionar o token precisa também de “Contents: leitura e escrita”." }),
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

/* ---------- ajustes ---------- */
function telaAjustes() {
  const repo = h("input", { id: "f-repo", value: cfg.repo, autocapitalize: "none", autocomplete: "off", spellcheck: "false" });
  const tok = h("input", { id: "f-tok", type: "password", value: cfg.token, placeholder: "github_pat_…", autocomplete: "off", spellcheck: "false" });
  const g = global();
  const conc = h("input", { type: "number", min: 1, max: 4, value: g.max_concorrencia || 1 }), ttl = h("input", { type: "number", min: 1, max: 168, value: g.ttl_espera_horas || 24 }), ret = h("input", { type: "number", min: 1, max: 90, value: g.retencao_dias || 14 });
  return h("div", {}, h("a", { class: "voltar", href: "#/mais" }, icone("back"), "Mais"), h("h2", { style: "margin-bottom:4px", text: "Conexão com o GitHub" }),
    h("label", { for: "f-repo", text: "Repositório" }), repo, h("label", { for: "f-tok", text: "Token do GitHub (opcional)" }), tok,
    h("p", { class: "dica", text: "Sem token você só acompanha. Com token também comanda os bots (executar, pausar, agendar, cancelar). Crie em GitHub → Settings → Developer settings → Fine-grained tokens, só para este repositório, com Actions: leitura e escrita (e Contents: leitura e escrita só se for adicionar sites de eventos). Fica guardado só neste aparelho." }),
    h("div", { class: "acoes" },
      h("button", { class: "btn prim", onclick: () => { cfg = { ...cfg, repo: repo.value.trim(), token: tok.value.trim() }; salvarCfg(cfg); aviso("Salvo."); atualizar(true); } }, "Salvar"),
      h("button", { class: "btn", onclick: async () => { cfg = { ...cfg, repo: repo.value.trim(), token: tok.value.trim() };
        try { const r = await fetch(`https://api.github.com/repos/${cfg.repo}`, cfg.token ? { headers: { Authorization: `Bearer ${cfg.token}` } } : {}); aviso(r.ok ? "Conexão ok." : `GitHub respondeu ${r.status}.`); } catch { aviso("Sem conexão com o GitHub."); } } }, "Testar")),
    h("h2", { style: "margin:28px 0 4px", text: "Regras gerais do Core" }),
    h("div", { class: "interruptor" }, h("span", { text: "Fuso dos horários" }), h("b", { text: g.timezone || TZ })),
    h("label", { text: "Bots rodando ao mesmo tempo (1 a 4)" }), conc, h("label", { text: "Tarefa esperando na fila expira em (horas)" }), ttl, h("label", { text: "Guardar histórico de tarefas por (dias)" }), ret,
    h("div", { class: "acoes" }, h("button", { class: "btn prim", onclick: () => comando({ acao: "config_global", campos: { max_concorrencia: parseInt(conc.value, 10), ttl_espera_horas: parseInt(ttl.value, 10), retencao_dias: parseInt(ret.value, 10) } }, { confirmar: "Salvar as regras gerais?" }) }, "Salvar regras")),
    h("p", { class: "dica", text: "Com mais de 1 bot ao mesmo tempo, workflows que gravam os mesmos arquivos de dados ainda se enfileiram no GitHub; deixe em 1 enquanto a cadeia antiga estiver ativa." }));
}

/* ---------- rotas ---------- */
const rota = () => { const p = location.hash.replace(/^#\/?/, "").split("/"); return { tela: p[0] || "geral", id: p[1] }; };
const TITULOS = { geral: "Visão geral", bots: "Bots", agenda: "Agendamentos", fila: "Fila de tarefas", mais: "Mais", dados: "Banco de dados", eventos: "Eventos", historico: "Histórico", logs: "Logs", fontes: "Fontes", custos: "Custos e consumo", ajustes: "Configurações", revisao: "Revisão", cobertura: "Cobertura geográfica", "em-breve": "Em breve" };
function desenhar() {
  const r = rota();
  const aba = { bot: "bots", dados: "mais", eventos: "mais", historico: "mais", logs: "mais", fontes: "mais", custos: "mais", ajustes: "mais", "em-breve": "mais", revisao: "mais", cobertura: "mais" }[r.tela] || r.tela;
  document.querySelectorAll(".abas a").forEach((a) => a.setAttribute("aria-current", a.dataset.tela === aba ? "page" : "false"));
  const caixa = document.getElementById("log-caixa"), colado = caixa && caixa.scrollTop + caixa.clientHeight >= caixa.scrollHeight - 8, y = window.scrollY;
  const telas = { cobertura: telaCobertura, revisao: telaRevisao, geral: telaGeral, bots: telaBots, agenda: telaAgenda, fila: telaFila, mais: telaMais, dados: telaDados, eventos: telaEventos, historico: telaHistorico, fontes: telaFontes, custos: telaCustos, ajustes: telaAjustes };
  const tela = r.tela === "bot" ? detalheBot(r.id) : r.tela === "logs" ? telaLogs(r.id) : r.tela === "em-breve" ? telaEmBreve(r.id) : r.tela === "cobertura" && r.id ? detalheCobertura(r.id) : (telas[r.tela] || telaGeral)();
  $main.replaceChildren(tela);
  const nova = document.getElementById("log-caixa"); if (nova && colado !== false) nova.scrollTop = nova.scrollHeight;
  window.scrollTo(0, y);
  document.getElementById("titulo").textContent = r.tela === "bot" ? meta(r.id).nome : (TITULOS[r.tela] || "Bot Control");
}
window.addEventListener("hashchange", () => { window.scrollTo(0, 0); desenhar(); if (!["ajustes"].includes(rota().tela)) atualizar(); });
document.getElementById("btn-atualizar").addEventListener("click", () => atualizar(true));
document.addEventListener("visibilitychange", () => { if (!document.hidden) atualizar(); });
setInterval(() => { if (!document.hidden && Date.now() - ultimaBusca >= (algumRodando() || ["bot", "fila"].includes(rota().tela) ? 8000 : 45000)) atualizar(); }, 4000);

if ("serviceWorker" in navigator && location.protocol.startsWith("http")) navigator.serviceWorker.register("sw.js").catch(() => {});
$main.replaceChildren(h("p", { class: "carregando", text: "Carregando os bots…" }));
atualizar();
window.__painel = { ST, CTL, desenhar };   // usado nos testes
})();
