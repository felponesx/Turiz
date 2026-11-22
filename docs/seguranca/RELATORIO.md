# TURIZ — Relatório de auditoria e segurança

**Data:** 22/11/2026 · **Escopo:** repositório `felponesx/Turiz` (API FastAPI, coletores, dados, CI) e protótipo do front (artefato). **Não há ambiente de produção ainda** (sem hospedagem, domínio, banco gerenciado, CDN/WAF).

## G. Status final: **CONTROLADO**
Proteções implementadas e **testadas** no código, no CI e no front; **não** declaramos o TURIZ seguro para lançamento público. Faltam itens que dependem de hospedagem e de decisões do dono (seção C), e a validação de XP/notas no servidor. Enquanto isso, o build de produção do front **desliga** XP, ranking, recompensas e notificações simuladas ("Em breve").
Escala: CRÍTICO · VULNERÁVEL · **CONTROLADO** · PREPARADO · VALIDADO. Para chegar a PREPARADO: infraestrutura (item F), backups de banco testados e validação de XP no servidor. VALIDADO exige teste de intrusão externo na infraestrutura real.

## A. Diagnóstico (o que encontramos)
| # | Sev. | Achado | Causa / impacto | Onde | Situação |
|---|---|---|---|---|---|
| 1 | **CRÍTICA** | Login `admin/admin` embutido no front e **qualquer** e-mail+senha(8+) "entrava" | Autenticação inexistente no protótipo; publicado = acesso livre | `turiz.html` (`submitAuth`) | **Contido**: flag `PROTO`; o build de produção remove o código e usa a API real (testado E2E) |
| 2 | **CRÍTICA** | XP, ranking, notas fiscais, recompensas e "usuários" rodam só no navegador | Forjável por qualquer pessoa; ranking/cupons falsos = "promessa falsa" | `turiz.html` | **Contido**: em produção viram "Em breve". **Pendente**: validação no servidor (libs prontas: `notas.py`, `fraude.py`) |
| 3 | **ALTA** | **XSS**: `p.cuisine` e outros campos entravam no HTML sem escape (≥ 6 pontos) + links `javascript:` aceitos em site/redes/cardápio | Dado externo (OSM/Receita/sites) poderia executar script na sessão | `turiz.html` | **Corrigido** (escape na saída + saneamento ao carregar + URLs só http(s)); teste dinâmico com payload em todos os campos: 0 execuções |
| 4 | **ALTA** | Limite de requisições contornável (`X-Forwarded-For` falso); só o módulo de eventos tinha limite | Scraping/DoS livres; **achado extra do teste de carga**: `uvicorn --proxy-headers` padrão confia no XFF de 127.0.0.1 | `eventos/api.py`, deploy | **Corrigido** (IP real, `TURIZ_PROXY_HOPS`, `--no-proxy-headers` documentado) |
| 5 | **ALTA** | Chave de API única, comparação não constante, sem bloqueio de força bruta, sem escopos, sem auditoria | Roubo/adivinhação da chave = controle total sem rastro | `main.py` | **Corrigido**: chaves com escopo, `hmac.compare_digest`, bloqueio progressivo, trilha de auditoria, ≥ 32 caracteres em produção |
| 6 | **ALTA** | Rotas caras sem proteção (`/lugares/geo` devolvia 24 mil linhas sem cache; buscas); `/ingest` sem limite de lote/corpo | DoS barato | `main.py` | **Corrigido**: limites por classe, semáforo (503), cache 5 min, lote ≤ 5.000, corpo ≤ 1 MB/8 MB |
| 7 | **ALTA (LGPD)** | Sem política de privacidade/termos, sem exportar/excluir dados, sem aviso de armazenamento | Descumprimento da LGPD | app | **Criado** (textos-base + endpoints + telas). **Pendente**: revisão jurídica e dados da empresa |
| 8 | **ALTA (continuidade)** | Sem backup testado, sem monitor externo, sem plano de incidente/recuperação | Perda de dados/indisponibilidade sem resposta | repo | **Criado** (teste real de restauração OK, workflows, planos) |
| 9 | MÉDIA | `/docs`, `/openapi.json` e `/health` com contagens públicos; sem cabeçalhos de segurança; 500 poderia vazar detalhes | Mapeamento da API e informações internas | `main.py` | **Corrigido** |
| 10 | MÉDIA | Curinga `%`/`_` em buscas; `offset` ilimitado; ids de caminho enormes davam **erro 500**; 422 ecoava a entrada (inclusive senhas) | Varredura de tabela, DoS, eco de dados | `main.py` | **Corrigido** (achados confirmados por teste de fuzz) |
| 11 | MÉDIA | Google Fonts, jsDelivr (jsQR) e Leaflet sem SRI | IP do visitante vai a terceiros; cadeia de suprimentos | front | **Corrigido** no build de produção (fontes e jsQR locais com hash, CSP por hash); Leaflet da página estática com SRI |
| 12 | MÉDIA | XML de servidor externo lido com parser padrão (XXE/expansão) em 2 coletores | Bomba de entidades | `coletar_receita.py`, `sondar_receita.py` | **Corrigido** (`defusedxml`) |
| 13 | MÉDIA | Repositório público sem Dependabot alerts, sem proteção contra *force-push*/exclusão da `main` | Histórico apagável; CVEs sem aviso | GitHub | **Pendente manual** (o ambiente bloqueia mudar configurações do repo). Secret scanning e push protection **já estavam ativos** |
| 14 | MÉDIA | Perda de contexto de privacidade: fotos de terceiros exibidas sem autorização formal | Pedidos de remoção/ação de titulares | dados | **Risco aceito pelo dono do projeto**, mitigado com crédito, link da origem e canal de remoção (aba *Imagens*) |
| 15 | BAIXA | Acessibilidade: `lang` ausente, nomes acessíveis incoerentes, contraste do botão no escuro, foco em folhas | WCAG 2.1 AA | front | **Corrigido** (axe: 0 violações em 13 telas × claro/escuro × celular/desktop; teste de teclado) |
| 16 | BAIXA | SHA-1 só como identificador (Bandit B324); `0.0.0.0` como origem local (B104) | Falsos positivos | coletores | Marcados (`usedforsecurity=False`, `nosec` justificado) |
| 17 | INFO | Token do compartilhamento público da Receita no repo; 2 registros OSM com "@" | Valores públicos por design | `receita.py`, dados | Documentado (allowlist do Gitleaks) |

## B. Correções executadas
**API** (`app/seguranca/*`, `app/main.py`): middleware ASGI (cabeçalhos CSP/nosniff/HSTS/Permissions-Policy/COOP/CORP, `no-store` em `/admin` e `/conta`, `X-Request-ID`), limitador de janela deslizante com bloqueio **progressivo e temporário** por IP e classe (leitura 240/min, cara 30/min, escrita 60/min, auth 8/10 min), limite de corpo, timeout de 30 s, semáforo de concorrência, erros 500 sem detalhes, 422 sem eco, CORS fechado, `TrustedHost` opcional, docs desligados, `/health` mínimo, ids limitados, curingas escapados, cache do mapa, ingest validado (lote, campos, URLs).
**Chaves e auditoria**: `TURIZ_API_KEYS` (escopos ingest < moderacao < admin), comparação em tempo constante, tabela `auditoria` (ator, rota, resultado, IP **pseudonimizado**, sem segredos).
**Contas** (`app/conta/*`): Argon2id, política de senha NIST, sessões de servidor (token só em hash, 30 d/7 d ociosa, teto de 10 dispositivos), cookie HttpOnly + SameSite + CSRF por HMAC + checagem de Origin, **MFA TOTP** (segredo cifrado, anti-replay, 8 códigos de recuperação em hash), **admin só com MFA**, bloqueio progressivo por conta e por IP, recuperação/troca de e-mail e senha **sem enumeração** (respostas e tempo equalizados), reautenticação para operações sensíveis, alerta de novo dispositivo, exportar/excluir (LGPD), favoritos isolados por dono (sem IDs de usuário em rota alguma).
**Uploads/notas/fraude** (bibliotecas prontas e testadas, ainda sem endpoint): `uploads.py` (formato real, bomba de descompressão, reencode sem EXIF/GPS, nome do servidor, sem path traversal, 0600, cota), `notas.py` (valida a chave, devolve só HMACs, **nunca guarda CNPJ**), `fraude.py` (sinaliza e retém, não bane).
**Banco**: migração `0003` aditiva (tabelas de contas/auditoria), `retencao.py` (auditoria 12 m, sessões 90 d, tokens 30 d), papéis de mínimo privilégio (`postgres-roles.sql`).
**Front**: escape/saneamento/URLs; sem handlers inline; **build de produção** (`build_producao.py`): `PROTO=false`, sem login de teste, sem exemplos, sem CDN, CSP por hash, com guardas (empresa preenchida + revisão jurídica); páginas legais (privacidade, termos, armazenamento, ingressos/reembolso, imagens, empresa); exportar/excluir dados; tela de segurança real (sessões, trocar senha, sair de todos); acessibilidade (foco preso nas folhas, nomes, contraste, `lang`).
**Repositório/CI**: Dependabot (pip + Actions), workflow *Segurança* (pytest, Bandit, pip-audit, Gitleaks no histórico completo, varredura de privacidade), CodeQL (Python + JS), backup + teste de restauração, monitor externo, vendor do front com hash.
**Dependências**: adicionadas `argon2-cffi`, `pyotp`, `cryptography`, `Pillow`; `pip-audit`: **nenhuma vulnerabilidade conhecida**.

## C. Pendências
| O que | Por quê / depende de | Custo |
|---|---|---|
| Hospedagem (API + Postgres + domínio) | Não existe | Provedor (decisão) |
| CDN/WAF/anti-DDoS, DNSSEC, TLS, firewall de origem | Depende da hospedagem (`infraestrutura.md`) | Cloudflare tem plano gratuito; WAF/bot management avançados são pagos |
| Backup do Postgres com PITR + cópia imutável fora do GitHub | Depende do provedor; defina `BACKUP_PASSPHRASE` e `BACKUP_S3_*` | Armazenamento (baixo) |
| Validação de XP/notas **no servidor** | Decisão de produto (regras de XP) + endpoint de experiência | Desenvolvimento |
| Provedor de e-mail (recuperação de senha) | Sem ele, o fluxo responde mas o e-mail não chega | SMTP/serviço transacional |
| Dependabot alerts/security updates, proteção da `main` (sem *force-push*/exclusão), *private vulnerability reporting* | Configurações do repositório (bloqueadas no ambiente de trabalho); **ative em Settings → Code security / Branches** | Grátis |
| 2FA na conta do GitHub, do registrador e do provedor | Só você | Grátis |
| Textos legais: **revisão jurídica**; preencher razão social, CNPJ **da empresa**, endereço, contato, encarregado, prazo de remoção | Só você/advogado (o build de produção recusa sem isso) | Honorários |
| Canal de segurança em `SECURITY.md` | Defina o e-mail | — |
| Contratos de operador e avaliação de transferência internacional | Depende do provedor | — |
| Teste de intrusão externo | Depende da infraestrutura real | Serviço pago |
| Fotos de terceiros | Autorização formal de uso (decisão sua, já anunciada) | — |

## D. Testes (executados em 22/11/2026)
| Teste | Resultado |
|---|---|
| `pytest tests`: **194 testes** (auth, contas, IDOR, CSRF, MFA, brute force, credential stuffing, rate limit, injeção/fuzz em todas as rotas GET, sessões forjadas/JWT *alg=none*, CORS, uploads maliciosos, notas, fraude, privacidade, migrações, retenção, restauração, monitor) | **194 aprovados** |
| Bandit (média/alta) / pip-audit | 0 / 0 vulnerabilidades |
| CI no GitHub: testes + Bandit + pip-audit + **Gitleaks (histórico completo)** + CodeQL (Python/JS) | **Todos verdes** (alertas do CodeQL só são legíveis na aba Security do repositório) |
| `scripts/verificar_privacidade.py` (CNPJ/CPF/e-mail em `data/`) | 0 ocorrências |
| **Restauração real** dos snapshots num banco novo | **OK**: 23.990 lugares e 71 eventos, `integrity_check` ok, 0 chaves estrangeiras quebradas, ~14 s |
| XSS dinâmico (payload em todos os campos externos, com e sem o saneador) | 0 execuções, 0 URLs `javascript:`, 0 injeções |
| E2E do front de produção + API real (CSP **enforçada**): cadastro, login, cookies, MFA de admin, exportar, segurança, bloqueio | **Tudo OK**, 0 violações de CSP |
| Acessibilidade (axe WCAG 2.1 A/AA, 13 telas × 2 temas × 2 tamanhos) + teclado | **0 violações**; foco preso nas folhas, Esc fecha |
| **Carga controlada** (1.500 req em ~10 s, 60 simultâneas, servidor local) | 1.470 recusadas com 429 + `Retry-After`, 0 erros 500/502/504, corpo de 500 KB recusado (413), servidor normal após a janela |
| Rollback de migração (`downgrade`) | Testado (`test_migracoes.py`) |
**Falhas encontradas durante os testes (e corrigidas):** erro 500 com ids enormes; 422 ecoando a entrada; limite de IP anulado por `--proxy-headers`; 5 pontos de XSS; foco que escapava das folhas; contraste do botão no escuro; `lang` ausente; cartões sem nome acessível coerente.
**Não executados** (dependem de infraestrutura/ações): teste de restauração do Postgres, DDoS volumétrico real, teste de intrusão externo, envio real de e-mail, SMTP.

## E. Segurança restante (riscos)
- **Sem hospedagem**, não há proteção de rede, DDoS volumétrico, TLS, DNS nem monitoramento ao vivo: **risco aberto** até existir.
- Limitador **em memória por processo**: com vários servidores o limite global precisa ser feito também na borda (CDN) ou em Redis.
- Bloqueio de conta por tentativas permite que um atacante **pause** a conta de alguém por até 15 min (troca de conveniência por proteção contra força bruta; mitigado pelo limite por IP e pela recuperação de senha).
- `style-src 'unsafe-inline'` na CSP do front (estilos em atributos): risco residual baixo de injeção de CSS.
- Fotos de terceiros em uso sem autorização formal (risco jurídico aceito, não técnico).
- Dados de OSM/Receita/sites são **não confiáveis por natureza**: o front os trata assim, mas qualquer novo campo exibido precisa de escape (há teste dinâmico para regressão).
- A auditoria cobre o que está no repositório e no protótipo; **não** cobre provedores ainda inexistentes.

## F. Infraestrutura (estado real)
Anti-DDoS: **não ativo** (configuração pronta em `infraestrutura.md`). Firewall/WAF: **não ativo**. Backups: workflow e teste de restauração **ativos**; cópia criptografada depende de `BACKUP_PASSPHRASE`; backup do Postgres **inexistente** (sem banco de produção). Monitoramento: workflow externo **ativo mas ocioso** até definir a variável `TURIZ_URL`; alertas por issue (e webhook opcional).

## Cruzamento com a lista "17 coisas" (captura enviada)
| # | Item | Situação |
|---|---|---|
| 1 Política de privacidade | Criada (rascunho para revisão) |
| 2 Termos de serviço | Criados (rascunho) |
| 3 Aviso de cookies | Aba "Armazenamento e cookies": só itens essenciais, **sem rastreadores**; aviso de transparência na 1ª abertura (produção) |
| 4 Política de reembolso | Aba "Ingressos": o TURIZ **não vende** ingressos; reembolso é do organizador |
| 5 Formulários na LGPD | Exportar/excluir/corrigir em Configurações; links de Termos/Privacidade no cadastro |
| 6 Só dados necessários | Mapa de dados em `dados-pessoais.md`; localização só no aparelho; nota fiscal só em hash; sem CNPJ |
| 7 Scripts de tracking | **Nenhum**; fontes e jsQR locais (sem Google Fonts/CDN no build de produção) |
| 8 Acessibilidade | axe 0 violações; foco e teclado testados |
| 9 Alt nas imagens | Fotos de lugar com `alt`; decorativas sem |
| 10 Contraste | Corrigido (AA) nos dois temas |
| 11 Navegação por teclado | Testada (Tab, Enter, Esc, foco preso e devolvido) |
| 12 Sem avaliações falsas | **Em produção os exemplos ficam desligados**; avaliações/ranking/cupons simulados viram "Em breve" |
| 13 Sem promessas falsas | Telas simuladas (segurança/2FA, recompensas, missões) removidas do build de produção |
| 14 Copyright das imagens | Crédito + link + canal de remoção; **autorização formal pendente (sua decisão)** |
| 15 Dados da empresa | Aba "Empresa"; o build **recusa** se razão social, CNPJ da empresa, endereço, contato e encarregado estiverem vazios |
| 16 Conformidade LGPD | Direitos implementados; **revisão jurídica e RIPD pendentes** |
| 17 Riscos jurídicos | Textos-base + checklist; **precisa de advogado** |
