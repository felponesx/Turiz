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

Endpoints: `GET /lugares`, `/lugares/geo`, `/lugares/{id}`, `/eventos`, `/health`; `POST /ingest/lugares` (header `x-api-key`).

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
