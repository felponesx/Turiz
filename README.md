# Turiz

API que coleta restaurantes, bares e eventos de São Paulo de várias fontes, guarda num banco (SQLite por padrão, Postgres via `DATABASE_URL`) e expõe endpoints para os bots.

## Fontes
| Fonte | Dados | Requisito |
|---|---|---|
| `osm` | restaurantes e bares | nenhum (Overpass) |
| `google` | restaurantes e bares, com nota | `GOOGLE_PLACES_API_KEY` (pago) |
| `eventbrite` | eventos das suas organizações | `EVENTBRITE_TOKEN` + `--orgs` |
| `sites` | eventos/lugares via JSON-LD das URLs de `sources.yml` | respeita robots.txt |

Obs.: a Eventbrite não tem mais busca pública, e o Sympla não tem API pública de busca. Para o Sympla, liste as páginas em `sources.yml` (se os termos permitirem).

## Uso
```bash
pip install -r requirements.txt
cp .env.example .env
python coletar.py osm sites    # coleta e atualiza data/*.json
API_KEY=segredo uvicorn app.main:app --reload
```
A API carrega `data/*.json` sozinha no primeiro start (banco vazio). Abra `http://localhost:8000/` para o app (busca, filtros, mapa) e `/docs` para a API.

Endpoints: `GET /lugares` (filtros `tipo`, `q`, `bairro`, `culinaria`, `aberto_agora`), `/lugares/geo`, `/lugares/{id}` (com `horario_estruturado` e `aberto_agora`),
`/lugares/{id}/cardapios`, `/lugares/{id}/eventos`, `/lugares/{id}/avaliacoes`, `/lugares/{id}/imagens`, `/lugares/{id}/redes`, `/eventos`, `/health`;
`POST /ingest/lugares`, `POST /avaliacoes`, `PATCH /avaliacoes/{id}`, `PATCH /imagens/{id}` (header `x-api-key`).

## Git
`.github/workflows/coleta.yml` roda toda segunda (ou manualmente) e commita os snapshots em `data/`. Configure os secrets `GOOGLE_PLACES_API_KEY` e `EVENTBRITE_TOKEN` no repositório.

## Bot de imagens
`python coletar_imagens.py commons site` reúne **referências** de fotos (url, autor, licença) em `data/imagens.json`; não baixa nem republica arquivos.

| Fonte | Origem | Status padrão |
|---|---|---|
| `commons` | Wikimedia Commons via tags `wikimedia_commons`/`wikidata` do OSM | `aprovada` se a licença for livre, senão `pendente` |
| `osm_image` | tag `image` do OSM (URL de outro site) | `pendente` |
| `site` | `og:image` do site do próprio estabelecimento (respeita robots.txt) | `pendente` |

`GET /lugares/{id}/imagens` devolve só as `aprovada` por padrão (`?status=todas`). `PATCH /imagens/{id}?status=aprovada|rejeitada` (header `x-api-key`) modera. Mostre sempre autor e licença ao exibir imagens do Commons. Fotos do Google Places têm termos próprios (não armazenar), por isso ficam de fora por enquanto.
Workflow: `.github/workflows/imagens.yml` (terças, ou manual).

## Automação (pipeline semanal)
Toda segunda 06:00 UTC: **Coleta agendada** (OSM + sites) → **Bot de enderecos** (bairro/CEP/rua) → **Bot de imagens**, encadeados e sem sobreposição (`concurrency: dados`). Cada etapa commita seus arquivos em `data/`. Depois, uma tarefa agendada do Claude sincroniza `data/` com o banco do app e avisa por push.
Qualquer etapa também roda manualmente em Actions → *Run workflow*.

## Bot de Instagram
`python coletar_instagram.py` vincula perfis do Instagram aos lugares **sem raspar o Instagram** (viola os termos e é bloqueado):
- `osm_tag`: tag `contact:instagram` do OpenStreetMap (confiança 0,90, `confirmado`);
- `site`: link para o Instagram no site oficial do lugar, respeitando robots.txt (0,70, `provavel`);
- `api_oficial`: com `INSTAGRAM_TOKEN` e `INSTAGRAM_USER_ID` (conta profissional sua ligada a uma página do Facebook), confere nome/site do perfil via Business Discovery e eleva para `confirmado` (0,98).
A API oficial não tem busca por nome: sem handle vindo do OSM ou do site, não há vínculo automático. `GET /lugares/{id}/redes` lista os perfis. Roda depois do bot de imagens no pipeline semanal.

## Bot de cardápios
`python coletar_cardapios.py [--limite-sites N] [--dry-run]` acha o cardápio **oficial** no site de cada lugar e guarda a referência em `data/cardapios.json`:
- `jsonld`: o site publica o cardápio em schema.org (itens e preços) → `confirmado`;
- `osm_tag`: tag `website:menu`/`menu:url` do OpenStreetMap → `confirmado`;
- `link_site`: link "Cardápio"/"Menu" na página inicial (próprio site, Goomer, MenuDino, Anota Aí, iFood, PDF ou imagem) → `provavel`.
Respeita robots.txt, visita só a página inicial e **não** segue Instagram/Facebook nem raspa o conteúdo de iFood e similares (só o link). Workflow: `cardapios.yml` (depois do bot de Instagram).

## Horários
`GET /lugares/{id}` devolve `horario_estruturado` (dias e faixas) e `aberto_agora`, a partir do `opening_hours` do OSM. Só interpreta regras simples (dias, faixas, `off`, `24/7`, `PH`); se for complexo demais devolve `null` e o texto bruto fica em `horario`. `GET /lugares?aberto_agora=true` filtra quem está aberto (fuso America/Sao_Paulo).

## Eventos (sistema inteligente de coleta)

Eventos reais de várias fontes, num só catálogo, sem inventar nada. Arquitetura:

- **Conectores independentes** (`app/eventos/conectores/`): `ticketmaster` (Discovery API v2), `jsonld` (sites com schema.org, respeita robots.txt),
  `feed_json`, `feed_xml`, `rss`, `planilha` (CSV/XLSX de organizadores) e `navegador` (Playwright, só para páginas que dependem de JavaScript;
  não contorna CAPTCHA/login/paywall: ao detectar, a fonte vira "bloqueada"). Uma fonte com erro não derruba as outras.
- **Cadastro de fontes** em `fontes_eventos.yml` (e `PUT /admin/eventos/fontes`, protegido por X-API-Key): intervalo, prioridade, autorização,
  saúde (`ok | erro | aguardando_credencial | bloqueada | desativada`). Organizadores/parceiros entram como uma entrada `feed_*`/`planilha`.
- **Banco** versionado com Alembic (`migracoes/`, aplicado no startup e em todos os scripts): `eventos` (evento canônico) + `evento_fontes`,
  `evento_fonte_links`, `evento_locais`, `evento_imagens`, `evento_artistas`, `evento_organizadores`, `evento_categorias`, `evento_atualizacoes`
  (histórico), `evento_coletas_log`, `evento_duplicatas` (fila de revisão). Índices por nome, categoria, local e data.
- **Duplicidade**: nome parecido não basta (precisa da mesma data e do mesmo local); o mesmo evento em várias fontes vira UM evento com vários links;
  dúvidas vão para `GET /admin/eventos/duplicatas` (resolver: `POST .../resolver?decisao=mesmo|distinto`). Nada é apagado: cancelados, adiados e
  encerrados ficam com status e histórico.
- **Categorias do TURIZ** (Música e entretenimento · Gastronomia · Cultura e lazer, com subcategorias; um evento pode ter várias): `app/eventos/taxonomia.py`.
- **API pública**: `GET /eventos` (filtros: `q, categoria, cidade, estado, pais, data_de, data_ate, preco_max, gratuito, tipo_local, local, lugar_id, fonte, com_imagem, ordem`),
  `GET /eventos/{id}`, `GET /eventos/categorias`, `GET /eventos/busca?q=shows hoje em São Paulo` (linguagem natural), `GET /lugares/{id}/eventos`.
  Eventos vencidos nunca aparecem como futuros; limite de requisições por IP.
- **Execução**: `python coletar_eventos.py sincronizar | rodar [--fonte SLUG] [--forcar] | fontes | duplicatas | validar-ticketmaster`.
  Workflow "Coleta de eventos" (a cada 6 h; cada fonte só roda quando vence o intervalo). Snapshot em `data/eventos_v2.json.gz`.

### Ticketmaster
Chave **somente** na variável de ambiente `TICKETMASTER_API_KEY` (GitHub: Settings → Secrets → Actions). Sem ela, a fonte fica `aguardando_credencial`.
A chave nunca vai ao front, às respostas da API, aos logs ou ao banco (há testes para isso). Só parâmetros documentados da Discovery API v2 são usados
(`geoPoint` em vez do `latlong` obsoleto; paginação limitada a size×page < 1000, com divisão da janela de datas; 5 req/s; reação a 429).
**A cobertura no Brasil só é conhecida com uma consulta real**: rode o workflow "Coleta de eventos" com "validar_ticketmaster" (ou
`python coletar_eventos.py validar-ticketmaster`) para ver quantos eventos existem no Brasil e em São Paulo.

### Testes
`pytest tests/eventos` (respostas da Ticketmaster SIMULADAS com `httpx.MockTransport`: provam o código, não a API real). Front: `frontend/teste_eventos_front.js`
(Playwright, mobile e desktop). `frontend/build_api_eventos.py` embute os eventos reais do snapshot no protótipo.

## Avaliações
Só avaliações **do próprio TURIZ**, enviadas pelo backend do app depois de uma experiência (`POST /avaliacoes`): três notas (comida, ambiente, atendimento), uma por nota fiscal; só aparecem `publicada`s e, por padrão, só as `validada`s. A tabela **não** é exportada para `data/` (repositório público) e a API nunca devolve o autor. Não guardamos notas de terceiros (Google, TripAdvisor, Foursquare...): os termos desses serviços costumam proibir guardar e republicar.

## Diagnóstico de fontes
`python diagnosticar_fontes.py` (ou Actions → *Diagnostico de fontes*) testa cada fonte candidata a partir do GitHub Actions e gera `FONTES.md` + `data/diagnostico_fontes.json`: abre? robots.txt permite? tem JSON-LD de eventos? precisa de chave? Use o relatório para decidir quais URLs entram em `sources.yml`.

## Segredos (opcionais)
`GOOGLE_PLACES_API_KEY`, `EVENTBRITE_TOKEN`, `TICKETMASTER_API_KEY`, `INSTAGRAM_TOKEN`, `INSTAGRAM_USER_ID` em Settings → Secrets → Actions. Sem eles, a fonte correspondente é simplesmente ignorada.

## Bot da Receita (amplia a base de bares e restaurantes)
`python coletar_receita.py [--arquivos 0,1,...,9]` lê os **dados abertos oficiais da Receita Federal** (CNPJ) e as coordenadas do **IBGE (CNEFE 2022)** e gera `data/lugares_receita.json.gz`: bares, restaurantes e lanchonetes (CNAE 5611-2/01 a 05) **ativos em São Paulo, com nome fantasia**. A coordenada vem do CNEFE por CEP + número (`extra.coordenada_aproximada` = `true` quando só há o centro do CEP). Workflow: `receita.yml` (todo dia 20 e manual).

**Privacidade (regra do projeto): o CNPJ de ninguém é gravado, exibido ou devolvido pela API.**
- O número do CNPJ existe só na memória, durante a ligação entre os arquivos da Receita, e é descartado. Os registros de saída nem têm esse campo.
- Não são lidos nem guardados: razão social (em MEI costuma ter o CPF da pessoa), e-mail, telefone (pode ser pessoal) e sócios.
- **MEIs e empresários individuais ficam de fora** por padrão: muitos funcionam na casa da própria pessoa e o endereço seria o endereço residencial dela.
- Uma trava (`validar_privacidade`) examina todos os registros antes de gravar e **aborta** se achar padrão de CNPJ, CPF, e-mail ou número longo em qualquer campo.
- O `fonte_id` é um hash do endereço e do nome (dados públicos), não do CNPJ. Os logs do Actions só mostram contagens.

Limites: "ativo na Receita" não garante que o lugar esteja aberto (pode ser só escritório ou cozinha de delivery) e a coordenada aproximada pode errar algumas centenas de metros. Lugares que já existem no OSM são tratados em `mesclar_com_osm`.

`python sondar_receita.py` (workflow *Sondagem Receita e IBGE*) mostra o formato dos arquivos sem imprimir nenhum dado real.
