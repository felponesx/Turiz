# TURIZ Cobertura Geográfica — Fase 5

Camada **independente de análise**: lê `data/*`, escreve só `data/coverage_*`. Não altera `lugares.json`, IDs nem os scores da Fase 4, e **não dispara nenhum scanner**.
Executar: `python coletar_cobertura.py` (~9 s) · Nuvem: workflow `cobertura.yml` (diário 07:10 Brasília, ou manual) · Distritos: `cobertura-fonte.yml` (manual, só quando a Prefeitura atualizar).

## Fonte e método territorial
- **Fonte**: GeoSampa / Prefeitura de São Paulo (WFS): `distrito_municipal` (96 distritos) e `subprefeitura`. A **zona** é o campo oficial `nm_regiao_05` (Centro 8, Norte 18, Sul 22, Leste 33, Oeste 15), sem classificação manual.
- **Unidade = distrito.** Não há malha oficial de **bairros**: o bairro fica `unknown` e o nome escrito no cadastro vira só `bairro_declarado`. Distrito nunca é tratado como bairro.
- Status por lugar: `confirmed` (coordenada precisa dentro do polígono, a ≥25 m da divisa) · `probable` (coordenada aproximada, mas o bairro declarado confere com o distrito) · `approximate` (coordenada aproximada da Receita) · `boundary_conflict` (perto da divisa: <25 m precisa, <150 m aproximada) · `unknown` (sem coordenada ou fora de SP).

## Fórmula do score de cobertura (0–100; pesos em `cobertura_config.yml`)
densidade 20 + diversidade 25 + confiabilidade média 15 + precisão territorial 15 + experiências 15 + atualidade 10.
- Densidade: `log(1+lugares/km²) / log(1+meta)`, meta = percentil 90 dos distritos (relativa, não absoluta); área limitada a 12 km² para distritos rurais. Nunca passa de 20 pontos.
- Diversidade: 0,5 riqueza (categorias com ≥2 lugares / 80% das categorias da cidade) + 0,3 equilíbrio (Shannon) + 0,2 especificidade (lugares com categoria além de restaurante/bar/lanchonete). Concentração (HHI) e categoria predominante são reportadas.
- Confiabilidade: média do score da Fase 4. Precisão: confirmed 1, probable 0,7, divisa 0,5, aproximada 0,3, unknown 0.
- Faixas: 80+ muito boa · 65 boa · 45 moderada · 25 baixa · 0 crítica. Menos de 5 lugares = **desconhecida** (falta informação).
- Prioridade (0–100): lacuna 30 + categorias ausentes 25 + pouca quantidade 15 + baixa confiabilidade 10 + potencial 10 (percentil de densidade, proxy) + tempo desde a última atualização dos dados 10. Intervalos de reexploração por faixa em `intervalos_dias`.

## Arquivos
`coverage_neighborhoods.json.gz` (distritos + geometria) · `coverage_metrics.json.gz` · `coverage_categories.json.gz` · `coverage_priorities.json.gz` · `coverage_history.json.gz` (snapshots por data + histórico de buscas) · `coverage_places.json.gz` (lugar → distrito) · `coverage_summary.json` (painel).
gzip sem timestamp: mesmo conteúdo = mesmos bytes. Rodar de novo no mesmo dia não duplica snapshot, prioridade nem lugar; só `coverage_summary.json` muda (hora de geração).

## API (FastAPI, ainda não hospedada) — `app/cobertura_api.py`
`GET /coverage`, `/coverage/neighborhoods[?zona&status]`, `/coverage/neighborhoods/{id}`, `/coverage/categories`, `/coverage/priorities`, `/coverage/history`, `/coverage/comparison`: exigem chave `moderacao`+. `POST /coverage/recalculate`: chave `admin`, uma execução por vez, intervalo mínimo de 5 min.

## Painel
Mais → Cobertura geográfica: mapa SVG por distrito (filtros por faixa e zona), listas de lacunas, prioridades, categorias e scanners sugeridos; toque no distrito abre o detalhe (score decomposto, categorias presentes/ausentes, recomendação, histórico, Atualizar análise, Exportar).

## Limites
Sem bairros oficiais; categorias só vêm do cadastro (o que ele não diz não é detectado, então "experiências" ficam subdetectadas); nenhuma busca por distrito foi feita (histórico de buscas vazio; `registrar_busca` está pronto para os scanners); "Pesquisar bairro/categoria" não existe até haver scanners que aceitem distrito.
