# TURIZ Geo Scanner — Fase 6

Pesquisa no OpenStreetMap (Overpass) os pares **distrito × categoria** mais prioritários da fila de cobertura (`coverage_priorities`) e grava o que achou em `data/descobertas.json.gz`.
Não altera `lugares.json`, IDs, scores da Fase 4 nem o app.

- **Executar**: `python coletar_geo.py [--max-tarefas 6] [--distrito 35 --categoria padaria]` · nuvem: `geo-scanner.yml` (diário 02:00 Brasília, ou manual/painel). Depois das buscas o workflow recalcula a cobertura.
- **Filtros por categoria** em `cobertura_config.yml → geo_scanner.filtros` (padaria, doceria, sorveteria, cafeteria, bar, mercado, diferenciado, street food, cozinhas japonesa/coreana/chinesa/italiana/mexicana/árabe, pizzaria, hamburgueria, churrascaria, vegetariana, nordestina, brasileira). Restaurante e lanchonete não têm busca: a coleta semanal do OSM já cobre.
- **Fluxo**: consulta pela caixa do distrito → descarta o que cai fora do polígono oficial → compara com `lugares.json` (mesmo ID do OSM = existente; mesmo nome no mesmo ponto = duplicado; nome parecido perto = possível duplicado; resto = novo). Só "novo" e "possível duplicado" viram descoberta.
- **Descoberta** = lugar achado, `publicavel: false`, aguardando validação. Não entra na cobertura nem no app até passar pelo Revisor (fase futura).
- **Sem desperdício**: cada busca vira registro no histórico (`coverage_history.buscas`: achados, novos, duplicados, rejeitados, duração, erro). Não repete antes do intervalo da faixa do distrito (`intervalos_dias`) e o intervalo **dobra a cada busca sem novidade** (até ×8). Execução manual só espera 1 hora.
- **Limites e proteção**: 6 buscas por execução, 5 s entre consultas, até 3 mirrors do Overpass com espera crescente, para depois de 3 falhas seguidas. Entradas (distrito, categoria) validadas por regex no workflow, no script e no Core; nunca interpoladas em shell.
- **Idempotente**: o mesmo achado não duplica; `descoberto_em` e o status ficam preservados.
- **Painel**: Mais → Descobertas (lista, filtros, link ao OSM) e, no detalhe do distrito, "Pesquisar este distrito" / "Pesquisar esta categoria" (com confirmação, via Core).
- **Limites**: só OpenStreetMap; uma categoria sem filtro não é pesquisada; aprovar/rejeitar descobertas ainda não existe.
