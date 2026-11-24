# TURIZ Intelligence — arquitetura (Fase 1: Core, agendador, fila e Bot Control)

Escolha de infraestrutura: **tudo no GitHub, sem custo e sem servidor**. Os bots continuam sendo workflows do GitHub Actions; o Core é um
ciclo de 10 minutos (`nucleo.yml`) que guarda seu estado num branch órfão (`bot-control`). Os dados e as regras já nascem em JSON portável
(dá para migrar para Postgres/Supabase depois sem refazer a lógica: só trocar `core/store.py`).

```
PAINEL (painel/, celular) ──comando JSON──► nucleo.yml (workflow_dispatch) ──► core.despachante
   ▲ lê control/*.json e status/*.json                 │ valida (core/comandos.py) e aplica em control/*.json (branch bot-control)
   │                                                    ▼
   │                                   agenda (core/agenda.py) → fila (core/fila.py) → lançador (core/lancador.py)
   │                                                    │ gh workflow run <bot>.yml  (encadear=false)
   └── status/<bot>.json (branch bot-status) ◄── workers: coletar_*.py  (bots/status.py: progresso, pausa do Core)
```

## Módulos e arquivos
| Peça | Onde | O que faz |
|---|---|---|
| Registro de bots | `bots/registry.py` (+ `control/bots.json` publicado) | lista os bots; bot novo aparece sozinho no painel e no Core com configuração padrão |
| Configuração persistente | `control/config.json` | geral (pausa, concorrência, fuso, retenção, retry) e por bot (ativo, gerenciado, prioridade, agenda, dependências, limites, região, categorias, reprocessamento) |
| Agendador | `core/agenda.py` | diária, semanal, intervalo, única, "depois de outro bot"; fuso America/Sao_Paulo; uma execução por ocorrência; atrasada até 6 h |
| Fila de tarefas | `control/fila.json`, `core/fila.py` | prioridade crítica>alta>normal>baixa, deduplicação, estados completos, retry com **backoff exponencial + jitter**, **dead-letter queue**, expiração, reprocessamento, limpeza só por regra explícita |
| Despachante | `core/despachante.py`, `.github/workflows/nucleo.yml` | reconcilia, agenda, respeita pausa/concorrência/dependências/bots rodando fora do Core, reserva a tarefa antes de disparar (no máximo uma vez) |
| Comandos | `core/comandos.py` | o painel não escreve nos arquivos: manda comandos que o Core valida (tipos, limites, nomes) |
| Pausa em todos os bots | `bots/status.py::pausado` | pausa geral ou bot desligado valem também para os que rodam por cron/cadeia; o bot registra "pausado" e termina com sucesso (a cadeia segue) |
| Painel | `painel/` | Geral, Bots, Agenda, Fila, Mais (banco, eventos, histórico, logs, fontes, custos, configurações) |

## Preservação
Os 12 bots e seus workflows/crons/cadeia continuam como estavam. Por padrão todo bot existente nasce `gerenciado: false`: o Core **não** o agenda
(para não rodar em dobro); ele só atua em tarefas pedidas pelo painel. Ao ligar "Agendado pelo Core" num bot antigo, retire antes o horário fixo dele.
Tarefas do Core disparam o workflow com `encadear=false` (não acionam a cadeia antiga).

## Limites conhecidos desta fase
- Precisão do agendador ≈ 10 min (cron do GitHub). Comandos do painel levam ~1 min para valer.
- GitHub guarda só 1 execução pendente por grupo de concorrência: o Core só inicia um bot quando nenhum bot de dados está rodando.
- Ainda não existem: scanners de descoberta (Instagram/Geo/Web/Social), Revisor com score, Deduplicador de lugares, Image/Location Check, cobertura geográfica,
  consumo de APIs pagas. Aparecem no painel como "em breve" (sem números inventados). Entram nas próximas fases.
- Evolução diária/semanal/mensal: usa o histórico real registrado (até 12 execuções por bot); a série longa se forma com o tempo.

## Operação
- Ciclo manual: Actions → "TURIZ Core (despachante)" → Run workflow (campo *comando* opcional, JSON).
- Local/simulação: `python -m core.despachante --local pasta --comando '{"acao":"pausar_tudo"}'`.
- Token do painel: Actions leitura+escrita (Contents só para adicionar sites de eventos).
