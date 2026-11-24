# TURIZ Review — Fase 4 (deduplicação, localização, score)

Três bots novos, no grupo "Revisão" do painel, rodando em `.github/workflows/revisao.yml` (diário 06:40 Brasília, ou manual/Core).
Só **leem** `data/lugares.json` (e imagens, redes, cardápios) e escrevem arquivos novos. Nada existente é alterado.

| Bot | Etapa | Saída |
|---|---|---|
| Deduplicador | `dedup` | `data/duplicados.json.gz` |
| Location Check | `local` | `data/localizacao.json.gz` |
| Revisor | `score` | `data/revisao.json.gz` (por lugar) e `data/revisao_resumo.json` (painel) |

Executar: `python revisar.py [--etapa tudo|dedup|local|score]` (cerca de 8 s para 24 mil lugares).

## Regras
- **Duplicado confirmado**: mesmo nome (sem acento/palavras genéricas) no mesmo ponto (≤60 m), ou mesmo telefone/site, ou mesma rua e número. O duplicado é *relacionado* ao registro canônico (prefere Google > OSM > sites > Receita, coordenada precisa, mais campos). Nada é apagado; IDs e origem ficam.
- **Franquias**: nomes com ≥4 pontos são tratados como rede; nunca são unidos sem o mesmo endereço. Mesma rua com números diferentes = "unidade diferente".
- **Possível duplicado**: nome parecido e muito perto, sem prova. Vai para revisão, não é unido.
- **Location Check**: coordenadas inválidas, fora de São Paulo, aproximadas (Receita/IBGE), sem rua/número/bairro/CEP, CEP inválido ou de fora da capital. Só aponta; não inventa.
- **Score 0–100** (pesos em `revisao/score.py`, `CONFIG`): fontes independentes 40, nome 10, localização 20, endereço 15, foto rastreável 10, atualidade 5; possível duplicado −8. Site, redes, cardápio e imagem do site contam como **uma** fonte ("oficial"). Duas fontes distintas que apontam o mesmo lugar (OSM + Receita) contam como confirmação independente.
- **Faixas**: 90–100 alta, 75–89 confiável, 50–74 necessita revisão, 25–49 baixa, 0–24 não confirmado.
- **Completude** (separada): núcleo 80 pts; site, telefone, horário, redes, foto e cardápio só somam (20 pts); faltar não penaliza.
- `publicavel` = não é duplicado, sem problema grave de localização e score ≥ 50.

## Limites desta fase (sem rodeios)
- O **App Sync ainda não usa** `publicavel`: o app continua recebendo o que recebia. Ligar o filtro é a Fase 9, para não mudar o app sem você ver os números.
- Não há lista caso a caso nem botões Aprovar/Rejeitar no painel (a tela Revisão mostra totais). Falta também o Image Check com verificação de URL (precisa de rede) e a deduplicação contra lugares de outras fontes ainda não coletadas.
- Coordenadas da Receita são aproximadas; por isso quase todo lugar só dessa fonte cai em "necessita revisão" — é o resultado honesto, não um defeito.
- Recuperação: os arquivos são recriados do zero a cada execução; basta rodar o workflow de novo.
