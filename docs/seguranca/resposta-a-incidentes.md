# Resposta a incidentes

## Classificação
| Nível | Quando | Meta de resposta | Exemplos |
|---|---|---|---|
| **P0** | Dados pessoais vazados/alterados, invasão confirmada, conta admin comprometida, ransomware, banco apagado | Agir **imediatamente** (minutos); comunicação interna em 1 h | Dump do banco público; commit de segredo em produção; admin sem MFA acessado por terceiro |
| **P1** | Indisponibilidade total ou vulnerabilidade CRÍTICA explorável, DDoS efetivo, fraude em massa de XP | 1 h para contenção | API fora do ar; bypass de autorização (IDOR); chave de API exposta |
| **P2** | Degradação parcial, vulnerabilidade ALTA sem exploração conhecida, falha de backup, credencial exposta sem uso | 4 h | Erros 500 em volume; backup falhando 2 dias; dependência com CVE alta |
| **P3** | Falha localizada, vulnerabilidade MÉDIA, fraude isolada, abuso de scraping | 2 dias úteis | Conta fraudando XP; pico de bots |
| **P4** | Melhoria, vulnerabilidade BAIXA/informativa, pedido de usuário (LGPD) | Backlog (até 30 dias; pedidos LGPD em até 15 dias) | Cabeçalho faltando; pedido de exportação |

## Procedimento (vale para todos os tipos)
1. **Detecção** — alerta do monitor externo (issue "incidente"), CodeQL/Gitleaks/Dependabot, relato de usuário/pesquisador, logs de auditoria.
2. **Classificação** — defina P0–P4 e um responsável (incident commander). Abra registro com data/hora (UTC) e tudo o que for feito.
3. **Contenção** — pare o dano sem apagar evidência: bloqueie IP/faixa no WAF, ative "modo sob ataque", desligue o endpoint afetado, suspenda a conta (reversível), pause workflows (`gh workflow disable`).
4. **Isolamento** — tire o componente comprometido da rede; congele o estado (snapshot do disco/banco) antes de qualquer correção.
5. **Revogação de credenciais** — gire TUDO que possa ter vazado: `TURIZ_API_KEYS`/`API_KEY`, `TURIZ_HMAC_KEY` (invalida CSRF e pseudonimização), `TURIZ_ENC_KEY` (re-cifre TOTP antes), senhas do banco, tokens do GitHub/Actions/provedor, chave da Ticketmaster. Revogue todas as sessões (`UPDATE sessoes SET revogada_em=now() WHERE revogada_em IS NULL`).
6. **Preservação de evidências** — exporte `auditoria`, logs do servidor/WAF/CDN e o histórico do Git; guarde cópia imutável (somente leitura) com hash.
7. **Investigação** — linha do tempo: primeiro acesso, vetor, o que foi lido/alterado (tabela `auditoria`, `evento_atualizacoes`, logs). Determine causa-raiz.
8. **Recuperação** — restaure de backup verificado (`recuperacao-de-desastres.md`), reimplante a partir de código limpo (commit conhecido), nunca reaproveite uma máquina comprometida.
9. **Avaliação de dados expostos** — quais tabelas/campos, quantos titulares, se havia dado pessoal (e-mail, nome, favoritos, sessões), se havia senha (só hash Argon2id), localização (não é guardada no servidor), notas (só hashes), CNPJ (não é guardado).
10. **Comunicação** — equipe → usuários afetados (o que aconteceu, que dados, o que fazer: trocar senha, encerrar sessões) → público, se necessário. Linguagem clara, sem minimizar.
11. **Notificação legal** — se houver risco ou dano relevante a titulares: comunicar a **ANPD e os titulares em prazo razoável** (LGPD art. 48; a ANPD orienta 3 dias úteis) — decisão do encarregado/jurídico. Mantenha registro do incidente (art. 37).
12. **Correção** — corrija a causa-raiz (não só o sintoma); acrescente teste automatizado que falhe com o problema.
13. **Teste** — rode `pytest`, Bandit, pip-audit, E2E; valide em ambiente de homologação.
14. **Retorno seguro** — reabra gradualmente (primeiro leitura, depois escrita), monitore de perto por 72 h.
15. **Relatório pós-incidente** — até 5 dias úteis: linha do tempo, causa-raiz, impacto, o que funcionou/falhou, ações com dono e prazo. Sem culpados; foco em processo.

## Roteiros por tipo
- **Invasão / acesso não autorizado**: 3, 4, 5 (todas as chaves + sessões), 6, 7. Verifique `auditoria` (resultado `negado`/`alerta`), contas admin sem MFA, deploys recentes.
- **Vazamento de dados**: 9 e 10/11 viram prioridade; descubra o vetor (backup público? IDOR? log?). Remova o dado exposto (inclusive de caches e do histórico do Git — reescrita de histórico só com orientação, mantendo cópia da evidência).
- **DDoS**: ative modo sob ataque/regras de rate limit no CDN/WAF, aumente cache de `/lugares/geo` e listas, reduza `TURIZ_LIM_*`, desligue buscas caras temporariamente (o app continua em modo degradado: ver `infraestrutura.md`).
- **Ransomware / banco comprometido**: isole, NÃO pague sem consultar jurídico/polícia; restaure do backup imutável; o banco público é reconstruível pelos snapshots em `data/` (`restaurar.py`), as contas dependem do backup do Postgres.
- **API key exposta**: revogue imediatamente (5), verifique `auditoria` do ator, procure uso indevido; gire também as chaves vizinhas.
- **Conta administrativa comprometida**: revogue sessões, force nova senha + novo MFA, revise tudo que o admin fez desde a data suspeita (`auditoria`).
- **Fraude (XP/notas/avaliações)**: reter XP, marcar para revisão (`fraude.py` sinaliza, não bane sozinho), invalidar notas duplicadas, revisar contas relacionadas, ajustar regras.
- **Perda de dados / indisponibilidade**: siga `recuperacao-de-desastres.md`.
