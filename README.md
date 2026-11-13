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

## Eventos
- `sites`: JSON-LD (schema.org `Event`) das URLs de `sources.yml`, agora com preço, categoria, imagem e link de ingresso;
- `ticketmaster` (opcional): API oficial, exige `TICKETMASTER_API_KEY`; só roda se você incluir a fonte (`python coletar.py ticketmaster`);
- cada evento é **vinculado ao restaurante/bar** onde acontece (`app/sources/vincular.py`, por distância e nome; na dúvida não liga). `GET /lugares/{id}/eventos`.

## Avaliações
Só avaliações **do próprio TURIZ**, enviadas pelo backend do app depois de uma experiência (`POST /avaliacoes`): três notas (comida, ambiente, atendimento), uma por nota fiscal; só aparecem `publicada`s e, por padrão, só as `validada`s. A tabela **não** é exportada para `data/` (repositório público) e a API nunca devolve o autor. Não guardamos notas de terceiros (Google, TripAdvisor, Foursquare...): os termos desses serviços costumam proibir guardar e republicar.

## Diagnóstico de fontes
`python diagnosticar_fontes.py` (ou Actions → *Diagnostico de fontes*) testa cada fonte candidata a partir do GitHub Actions e gera `FONTES.md` + `data/diagnostico_fontes.json`: abre? robots.txt permite? tem JSON-LD de eventos? precisa de chave? Use o relatório para decidir quais URLs entram em `sources.yml`.

## Segredos (opcionais)
`GOOGLE_PLACES_API_KEY`, `EVENTBRITE_TOKEN`, `TICKETMASTER_API_KEY`, `INSTAGRAM_TOKEN`, `INSTAGRAM_USER_ID` em Settings → Secrets → Actions. Sem eles, a fonte correspondente é simplesmente ignorada.
