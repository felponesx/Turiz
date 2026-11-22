# Infraestrutura: o que existe, o que falta e como configurar

> **Estado real hoje:** o TURIZ ainda **não tem hospedagem de produção** (API, banco, domínio). O que existe é o código, o CI e o protótipo. Por isso
> WAF, anti-DDoS, firewall de rede, DNS, TLS, banco gerenciado e monitoramento ativo **não estão em operação**; abaixo está a configuração a aplicar
> quando houver hospedagem, e o que o código já faz independentemente dela.

## 1. Camadas (de fora para dentro)
| Camada | Responsável | Estado |
|---|---|---|
| **DNS e domínio** | Registrador + DNS (ex.: Cloudflare) | Pendente: **DNSSEC**, bloqueio de transferência (registrar lock), 2FA no registrador, CAA record, e-mail do titular monitorado |
| **CDN + WAF + anti-DDoS** | Cloudflare/equivalente | Pendente (ver 2) |
| **TLS** | CDN + origem | Pendente: TLS 1.2+, HSTS (o app já envia com `TURIZ_ENV=production`), certificado com alerta de validade (o monitor já checa) |
| **Proxy reverso / API** | uvicorn atrás de nginx/caddy ou PaaS | Código pronto: cabeçalhos, limites, timeouts, erros seguros |
| **Banco Postgres** | Gerenciado, rede privada | Pendente (ver 4) |
| **Segredos** | Gerenciador do provedor/GitHub Secrets | Pendente: rotação a cada 90 dias |

## 2. CDN/WAF/anti-DDoS (a configurar)
- **Proxy ligado** (nuvem laranja) e origem **aceitando só IPs do CDN** (allowlist no firewall) — senão o ataque vai direto na origem.
- **Rate limiting na borda** por IP: 300 req/min geral; 30 req/min em `/lugares/geo`, `/eventos/busca` e qualquer `?q=`; 10 req/min em `POST /conta/login|cadastro|recuperar`. (A API repete esses limites por processo — defesa em profundidade.)
- **WAF**: conjunto gerenciado OWASP + regras de SQLi/XSS; bloquear métodos inesperados; limite de corpo 1 MB (8 MB só em `/ingest/*` e só para IPs dos coletores).
- **Modo "sob ataque"** (desafio JS) acionável em 1 clique; **bot management** moderado para scraping de `/lugares` (permitir buscadores legítimos).
- **Cache**: `GET /lugares/geo` e listas públicas com cache de 5 min na borda (a API já envia `Cache-Control: public, max-age=300` no mapa). Dados de `/conta/*` e `/admin/*` **nunca** em cache (`no-store` já enviado).
- Configure `TURIZ_PROXY_HOPS=1` (ou o nº de proxies) para a API enxergar o IP real; sem isso o limite por IP usa o IP do proxy.
- Bloqueios **temporários e progressivos** (já no código); evite listas permanentes que prejudiquem usuários legítimos (CGNAT, redes móveis).

## 3. Resiliência e modo degradado
Sob falha, o TURIZ continua útil com o que não depende do componente que caiu:
| Se cair... | Continua funcionando | Fica indisponível |
|---|---|---|
| Ticketmaster/qualquer fonte de eventos | Tudo; eventos já coletados (a coleta é isolada por fonte) | Eventos novos dessa fonte |
| Banco de contas | Front público lê os **snapshots embutidos** (lugares, eventos, fotos, cardápios) | Login, favoritos na nuvem, exportar/excluir |
| API inteira | O front de produção é **estático** com os dados embutidos | Contas e dados novos |
| Provedor de e-mail | Login e uso normal | Recuperação de senha/alertas (respostas continuam genéricas) |
| Serviços de mapa/imagens de terceiros | Fotos embutidas (miniaturas locais); mapa esquemático interno | Fotos remotas das 19 imagens não baixadas |
O código aplica: timeout por requisição (30 s), semáforo de concorrência para rotas caras (503 + `Retry-After` quando saturado), cache do mapa, limites por IP/classe e `/health` leve para *health checks* e recuperação automática (configure o orquestrador para reiniciar em 3 falhas).

## 4. Banco de dados (Postgres)
- **Sem acesso público**: só a rede privada/VPC do app; `listen_addresses` restrito; `pg_hba.conf` por IP/rede; TLS obrigatório (`sslmode=require` na `DATABASE_URL`).
- **Papéis separados e mínimo privilégio** (`docs/seguranca/postgres-roles.sql`): `turiz_app` (CRUD nas tabelas, sem DDL), `turiz_migrador` (DDL, só no deploy), `turiz_leitura` (BI/relatórios), `turiz_backup` (somente leitura). O app nunca roda como dono do banco.
- Consultas **parametrizadas** (SQLAlchemy ORM; `LIKE` com curingas escapados) — verificado por teste.
- Limite de conexões por papel, `statement_timeout` (10 s no papel do app), `idle_in_transaction_session_timeout`.
- Criptografia em repouso (disco do provedor) + em trânsito (TLS) + campos sensíveis cifrados na aplicação (TOTP).
- Logs de alterações sensíveis: tabela `auditoria` (aplicação) + `pgaudit` para DDL e papéis (provedor).
- Monitorar: conexões, locks, tamanho, replicação, falhas de login.

## 5. Hardening do host/container
Usuário não-root; sistema de arquivos somente leitura exceto `/tmp` e a pasta de uploads (sem execução, `noexec`); portas: só 443 do CDN → proxy → app (porta da API **não** exposta); sem SSH por senha (chaves + MFA/bastion); atualizações automáticas de segurança; imagens fixas por digest; `pip-audit` no CI; sem `--reload`; variáveis de ambiente só de gerenciador de segredos.
Exemplo de execução: `TURIZ_ENV=production TURIZ_PROXY_HOPS=1 uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --timeout-keep-alive 5 --limit-concurrency 200 --no-proxy-headers`.
**Atenção:** use `--no-proxy-headers` e deixe o TURIZ decidir em quem confiar via `TURIZ_PROXY_HOPS`. Com o padrão do uvicorn (`--proxy-headers`), qualquer cliente que conecte de 127.0.0.1 passa a ter o `X-Forwarded-For` aceito às cegas — foi o que nosso teste de carga revelou: o limite por IP deixava de valer. O proxy/CDN na frente deve **sobrescrever** (não acrescentar a) `X-Forwarded-For` com o IP real que viu.

## 6. Ambientes e segredos
`dev` (SQLite local, chaves de teste) · `homologação` (Postgres próprio, dados fictícios, `build_producao.py --permitir-pendente`) · `produção`. **Segredos nunca compartilhados** entre ambientes; GitHub Environments com aprovação para publicar produção; chave de coletor (`ingest`) separada da de moderação e de admin.

## 7. Checklist de lançamento (tudo precisa estar ✔)
- [ ] Domínio com 2FA, DNSSEC, registrar lock · [ ] CDN/WAF/rate limit/regras de bot ativos · [ ] Origem só aceita o CDN
- [ ] `TURIZ_ENV=production`, `TURIZ_HMAC_KEY`, `TURIZ_ENC_KEY`, `TURIZ_API_KEYS` (32+ chars), `TURIZ_ALLOWED_HOSTS`, `TURIZ_PROXY_HOPS`, `TURIZ_CSP_PAGINA`
- [ ] Postgres com papéis mínimos, TLS, PITR e **teste de restauração feito** · [ ] Backup criptografado fora do GitHub
- [ ] `TURIZ_URL` definido (monitor externo) + webhook de alerta · [ ] Primeiro admin criado (`python -m app.conta.cli`) **com MFA**
- [ ] Provedor de e-mail configurado (recuperação de senha) · [ ] Textos legais revisados + dados da empresa preenchidos
- [ ] Validação de XP/notas **no servidor** (ver relatório) ou áreas de XP ocultas (já "Em breve" no build de produção)
- [ ] Dependabot alerts/security updates, proteção de branch e *private vulnerability reporting* ativos
