# TURIZ Intelligence — Inventário do sistema existente

Auditoria feita em 2026-11-24, antes de qualquer alteração para a plataforma "TURIZ Intelligence". Só leitura.
Resumo: **boa parte da base já existe** (bots, cadeia, painel, eventos com deduplicação, segurança). O que falta é a camada
central de **controle persistente** (registro de bots, configuração, fila, agenda editável, revisão e score) e os bots de **descoberta**.

## 1. Arquitetura atual (como as peças se falam)

```
GitHub Actions (cron / manual / dispatch)  ──►  bot (Python) ──►  SQLite temporário (restaurado de data/*.json)
        │                                           │                         │
        │ gh workflow run (próximo elo)             │ progresso a cada ~20 s  │ exporta de volta
        ▼                                           ▼                         ▼
   cadeia de 7 bots                      branch `bot-status` (status/<bot>.json)     data/*.json  ──git push──►  main
                                                    │                                        │
                                        painel/ (PWA no celular)               tarefa agendada do Claude (diária)
                                        lê status, dispara workflows           ──► atualiza blocos de dados do app (Artifact)
```

- **Execução**: GitHub Actions (grátis, na nuvem, independe do celular). Não há servidor próprio nem banco persistente.
- **"Banco"**: os arquivos `data/*.json` versionados no git. A cada execução um SQLite temporário é reconstruído (`restaurar.py`), o bot grava nele (upsert) e exporta de volta.
- **API** (FastAPI, `app/`): completa (lugares, eventos, imagens, redes, cardápios, avaliações, contas, MFA, auditoria), **mas não está hospedada** — hoje só roda localmente/testes.
- **App**: página única (Artifact do claude.ai, ~8 MB) com os dados **embutidos** em blocos `<!--API-...-->`, atualizados por `frontend/build_api_all.py`.
- **Painel**: `painel/` (PWA estático). Lê `status/<bot>.json` do branch `bot-status`; com token do GitHub roda/cancela bots e adiciona fontes de eventos.

## 2. Workflows e agendas (18)

| Workflow | Gatilho | Observação |
|---|---|---|
| Coleta agendada (OSM, sites, Ticketmaster) | segunda 06:00 UTC (03:00 Brasília) + manual | início da cadeia semanal |
| Bot de endereços → imagens → redes sociais → cardápios → fotos → Google Places | disparados em sequência pelo anterior (`gh workflow run`) | `workflow_run` não serve: o GitHub corta em 3 níveis |
| Coleta de eventos | a cada 6 h (:17) + manual | cada fonte só roda quando vence o intervalo de `fontes_eventos.yml` |
| Bot da Receita (CNPJ + IBGE) | dia 20, 03:00 UTC + manual | |
| Fotos ilustrativas, Diagnóstico de fontes, Testar fonte, Sondagem Receita | só manual | |
| Backup e teste de restauração | diário 03:37 UTC | |
| Segurança (testes, Bandit, pip-audit, Gitleaks, privacidade) | diário 05:23 UTC | |
| CodeQL | segunda 04:41 UTC | |
| Monitoramento externo | a cada 15 min | |
| Vendor do front | manual | |
| **Tarefa agendada do Claude** "Atualizar app Turiz" | diária 11:07 Brasília | roda fora do GitHub; publica no Artifact |

Concorrência: todos os bots de dados usam `concurrency: dados` (um por vez; o GitHub guarda só **1 pendente** — um terceiro cancela o segundo).

## 3. Bots e scripts

| Bot (id no painel) | Script | Fonte | Saída |
|---|---|---|---|
| osm | `coletar.py osm` | OpenStreetMap/Overpass (grade 4×4) | `data/lugares.json` |
| sites | `coletar.py sites` | JSON-LD dos sites em `sources.yml` | `data/lugares.json` |
| google | `coletar.py google` | Google Places API (precisa de chave) | `data/lugares.json` |
| receita | `coletar_receita.py` | Receita Federal + IBGE (sem CNPJ, sem MEI) | `data/lugares_receita.json.gz` |
| enderecos | `coletar_enderecos.py` | Nominatim (1 req/s) | `data/lugares.json` |
| imagens | `coletar_imagens.py` | Commons + `og:image` dos sites | `data/imagens.json` |
| instagram (redes) | `coletar_instagram.py` | tag do OSM + links no site oficial (+ API oficial com credencial) | `data/redes_sociais.json` |
| cardapios | `coletar_cardapios.py` | link/JSON-LD/PDF no site oficial | `data/cardapios.json` |
| fotos | `coletar_fotos.py` | baixa miniaturas das imagens aprovadas | `data/fotos/` |
| fotos_exemplo | `coletar_fotos_exemplo.py` | Commons por tema | `data/fotos_exemplo/` |
| eventos | `coletar_eventos.py` | 7 conectores (ticketmaster, jsonld, feeds, planilha, navegador) | `data/eventos_v2.json.gz` + `eventos.json` |
| turiz_app | tarefa do Claude + `scripts/atualizar_app_turiz.py` | `data/*` | blocos do app |

Infra de bots: `bots/status.py` (progresso %, itens, contagens, log, histórico, batimento), `bots/registry.py` (registro **estático em código**), `bots/cli.py`.

## 4. Onde os dados ficam e como chegam ao GitHub

- Estado: `data/*.json` (lugares 12,9 MB / 24.090 registros; Receita 19.166 em `.gz`; imagens 158; redes 293; cardápios 308; eventos 84; 200 miniaturas) e SQLite efêmero.
- Envio: `scripts/commitar_dados.sh` (sincroniza com o remoto, manda só os arquivos do bot, repete se outro envio chegar no meio).
- Esquema do banco: Alembic (`migracoes/`, 3 revisões). Tabelas: lugares, eventos, imagens, redes_sociais, cardapios, avaliacoes, 14 de eventos v2 (fontes, locais, categorias, atualizações, coletas_log, duplicatas…), contas/sessões/auditoria/favoritos.

## 5. Já existe e corresponde ao que a especificação pede

- Bots independentes, executáveis individualmente (manual), com logs, contagens e histórico (painel).
- Cadeia sequencial com tolerância a falhas e envio robusto de dados.
- **Eventos**: cadastro de fontes com saúde, intervalo e prioridade; deduplicação com fila de revisão; ciclo de vida (ativo/encerrado/cancelado, nada é apagado); categorias; busca em linguagem natural.
- Cobertura parcial de Geo (OSM), Web (sites), Menu (cardápios), Image (imagens/fotos), Social (links publicados pelo próprio lugar).
- Painel mobile-first (executar, cancelar, ver andamento, adicionar fonte).
- Segurança: chaves com escopo (`ingest < moderacao < admin`), auditoria, Argon2id, MFA, LGPD, privacidade do CNPJ, CI de segurança.
- Política de imagens (`politicas.yml`): sem aprovação manual.

## 6. Falhas, limites e pontos frágeis encontrados

1. **Sem estado central persistente**: não há banco/fila/registro editável. Agenda e configuração de cada bot estão **dentro dos YAML** (cron fixo em UTC); mudar horário exige editar workflow.
2. **Sem fila de tarefas**: a "fila" é o `concurrency` do GitHub (1 pendente; um disparo extra cancela outro). Não há prioridade, retry com backoff, dead-letter nem retomada por tarefa.
3. **Registro de bots estático** (`bots/registry.py`): adicionar bot exige editar código e regenerar o painel.
4. **Lugares sem revisão**: não há score de confiabilidade, nem deduplicação de **lugares** (só de eventos), nem status por registro; só `status` em imagens/redes/cardápios.
5. **Bot "Instagram" não descobre**: só liga perfis já publicados pelo lugar. Não há descoberta por região/categoria/termo nem registro de cobertura.
6. **OSM**: Overpass público falha com 504 (já corrigido: região ruim não derruba o resto). Sem registro de cobertura por região/categoria.
7. **Cadeia** mal projetada originalmente (`workflow_run` em 6 níveis); corrigida com `gh workflow run`.
8. **Escala dos dados no git**: `lugares.json` com 13 MB reescrito a cada ciclo; cresce com a base. A página do app (8 MB) tem teto de 16 MB.
9. **API não hospedada**: o app não consome API; recebe dados embutidos (1 publicação/dia pela tarefa do Claude).
10. **Custos/consumo**: nada medido (minutos de Actions, chamadas de API, quota Google/Ticketmaster).
11. Fontes instáveis: Visite São Paulo (timeout), Sympla/Eventbrite/Sesc bloqueiam robôs, Google Places aguardando chave válida, Ticketmaster aguardando chave.
12. O painel não mostra agenda editável, fila, revisão, cobertura nem custos (só status por bot).

## 7. Mapa: especificação → estado atual

| Módulo da especificação | Estado | Onde / lacuna |
|---|---|---|
| TURIZ CORE (registro, estados, distribuição) | parcial | `bots/registry.py` estático + `status/*.json`; falta registro/estado persistente editável |
| SCHEDULER | parcial | cron fixo nos YAML; falta agenda editável pelo painel, dependências declarativas, timezone configurável |
| TASK QUEUE | ausente | só `concurrency`; falta fila com prioridade/retry/dead-letter |
| BOT WORKERS | existe | scripts `coletar_*.py` + workflows |
| TURIZ REVIEW (revisão, score, dedup de lugares) | ausente (eventos têm dedup) | |
| TURIZ DATA HUB | parcial | `data/*.json` + SQLite efêmero; sem histórico por registro de lugares |
| APP SYNC | existe | tarefa diária + `atualizar_app_turiz.py` |
| BOT CONTROL (painel) | parcial | `painel/` cobre bots e status; faltam agenda, fila, descobertas, revisão, custos |
| Bot 01 Instagram Scanner | parcial | só vinculação; falta descoberta em camadas e cobertura |
| Bot 02 Geo Scanner | parcial | OSM existe; falta cobertura por região/categoria e cache |
| Bot 03 Web Scanner | parcial | `sites.py` + eventos jsonld; falta descoberta por guias/notícias |
| Bot 04 Social Scanner | ausente | |
| Bot 05 Event Scanner | existe | sistema de eventos v2 |
| Bot 06 Menu Scanner | parcial | falta itens/preços e detecção de mudanças em escala |
| Bot 07 Revisor | ausente | |
| Bot 08 Deduplicador (lugares) | ausente | lógica de eventos reaproveitável |
| Bot 09 Image Check | parcial | `fotos` valida download; falta classificação e verificação de correspondência |
| Bot 10 Location Check | ausente | (texto da especificação chegou cortado aqui) |

## 8. Regra de preservação — o que não pode quebrar

Workflows e agendas acima; arquivos `data/*`; `bots/status.py` e o branch `bot-status`; `painel/`; `scripts/commitar_dados.sh`;
`scripts/atualizar_app_turiz.py` e a tarefa diária; sistema de eventos v2 e suas tabelas; API, contas e segurança; testes (212).
Toda mudança: aditiva, atrás de migração Alembic, com testes e sem alterar o formato dos arquivos que o app já consome.
