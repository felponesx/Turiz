# Guia SP API

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
python restaurar.py            # carrega data/*.json no banco
python coletar.py osm sites    # coleta e atualiza data/*.json
API_KEY=segredo uvicorn app.main:app --reload
```
Endpoints: `GET /lugares`, `/lugares/{id}`, `/eventos`, `/health`; `POST /ingest/lugares` (header `x-api-key`).

## Git
`.github/workflows/coleta.yml` roda toda segunda (ou manualmente) e commita os snapshots em `data/`. Configure os secrets `GOOGLE_PLACES_API_KEY` e `EVENTBRITE_TOKEN` no repositório.
