window.BOTS_REGISTRY = {
 "grupos": [
  "Lugares",
  "Enriquecimento",
  "Revisão",
  "Inteligência",
  "Eventos",
  "Sistema Turiz"
 ],
 "bots": [
  {
   "id": "osm",
   "encadeia": true,
   "entradas": {
    "fontes": "osm"
   },
   "nome": "Restaurantes e bares",
   "fonte": "OpenStreetMap",
   "grupo": "Lugares",
   "icone": "pin",
   "descricao": "Varre São Paulo em regiões e capta restaurantes, lanchonetes, cafés e bares com nome, endereço, telefone, site e horário.",
   "workflow": "coleta.yml",
   "agenda": "segunda 03:00 (Brasília)",
   "requer": [],
   "saidas": [
    "data/lugares.json"
   ]
  },
  {
   "id": "receita",
   "nome": "Lugares da Receita Federal",
   "fonte": "Receita + IBGE (dados abertos)",
   "grupo": "Lugares",
   "icone": "building",
   "descricao": "Amplia a base com bares e restaurantes ativos em São Paulo (sem CNPJ, sem MEI) e coordenadas do IBGE.",
   "workflow": "receita.yml",
   "agenda": "dia 20 de cada mês",
   "requer": [],
   "saidas": [
    "data/lugares_receita.json.gz"
   ]
  },
  {
   "id": "sites",
   "encadeia": true,
   "entradas": {
    "fontes": "sites"
   },
   "nome": "Lugares em sites",
   "fonte": "Sites (JSON-LD)",
   "grupo": "Lugares",
   "icone": "globe",
   "descricao": "Lê dados estruturados de restaurantes e bares publicados em sites listados em sources.yml.",
   "workflow": "coleta.yml",
   "agenda": "junto com a coleta semanal",
   "requer": [],
   "saidas": [
    "data/lugares.json"
   ]
  },
  {
   "id": "google",
   "nome": "Google Places",
   "fonte": "Google Places API",
   "grupo": "Lugares",
   "icone": "star",
   "descricao": "Capta lugares com nota e número de avaliações. Só roda com a chave GOOGLE_PLACES_API_KEY (Places API ativada e faturamento).",
   "workflow": "google.yml",
   "agenda": "segunda, depois da coleta",
   "requer": [
    "GOOGLE_PLACES_API_KEY"
   ],
   "saidas": [
    "data/lugares.json"
   ]
  },
  {
   "id": "enderecos",
   "encadeia": true,
   "nome": "Endereços",
   "fonte": "Nominatim (OpenStreetMap)",
   "grupo": "Enriquecimento",
   "icone": "map",
   "descricao": "Completa bairro, CEP e rua pelas coordenadas. Nunca inventa número de casa.",
   "workflow": "enderecos.yml",
   "agenda": "depois da coleta semanal",
   "requer": [],
   "saidas": [
    "data/lugares.json"
   ]
  },
  {
   "id": "imagens",
   "encadeia": true,
   "nome": "Imagens dos lugares",
   "fonte": "Wikimedia Commons + sites",
   "grupo": "Enriquecimento",
   "icone": "image",
   "descricao": "Reúne referências de fotos (link, autor, licença) do Commons e da imagem de capa do site de cada lugar.",
   "workflow": "imagens.yml",
   "agenda": "depois dos endereços",
   "requer": [],
   "saidas": [
    "data/imagens.json"
   ]
  },
  {
   "id": "instagram",
   "encadeia": true,
   "nome": "Redes sociais",
   "fonte": "Sites e OpenStreetMap",
   "grupo": "Enriquecimento",
   "icone": "share",
   "descricao": "Liga cada lugar ao perfil de Instagram (e outras redes) publicado pelo próprio lugar. Não raspa redes sociais.",
   "workflow": "instagram.yml",
   "agenda": "depois das imagens",
   "requer": [],
   "saidas": [
    "data/redes_sociais.json"
   ]
  },
  {
   "id": "cardapios",
   "encadeia": true,
   "nome": "Cardápios",
   "fonte": "Sites dos lugares",
   "grupo": "Enriquecimento",
   "icone": "menu",
   "descricao": "Acha o cardápio oficial no site de cada lugar (itens e preços quando o site publica).",
   "workflow": "cardapios.yml",
   "agenda": "depois das redes sociais",
   "requer": [],
   "saidas": [
    "data/cardapios.json"
   ]
  },
  {
   "id": "fotos",
   "encadeia": true,
   "nome": "Fotos (miniaturas)",
   "fonte": "Imagens captadas",
   "grupo": "Enriquecimento",
   "icone": "photo",
   "descricao": "Baixa e reduz as fotos de lugares e eventos para o app não depender do site de origem.",
   "workflow": "fotos.yml",
   "agenda": "depois dos cardápios",
   "requer": [],
   "saidas": [
    "data/fotos/"
   ]
  },
  {
   "id": "fotos_exemplo",
   "nome": "Fotos ilustrativas",
   "fonte": "Wikimedia Commons",
   "grupo": "Enriquecimento",
   "icone": "photo",
   "descricao": "Fotos de licença livre por tema (pizza, show, bar...) para lugares e eventos sem foto própria.",
   "workflow": "fotos-exemplo.yml",
   "agenda": "sob demanda",
   "requer": [],
   "saidas": [
    "data/fotos_exemplo/"
   ]
  },
  {
   "id": "deduplicador",
   "entradas": {
    "etapa": "dedup"
   },
   "nome": "Deduplicador",
   "fonte": "Base de lugares",
   "grupo": "Revisão",
   "icone": "copy",
   "descricao": "Acha lugares repetidos (mesmo nome no mesmo ponto, mesmo telefone/site) e relaciona ao registro principal, sem apagar nada. Unidades diferentes de uma rede nunca são unidas.",
   "workflow": "revisao.yml",
   "agenda": "diário, depois das coletas",
   "requer": [],
   "saidas": [
    "data/duplicados.json.gz"
   ]
  },
  {
   "id": "location_check",
   "entradas": {
    "etapa": "local"
   },
   "nome": "Location Check",
   "fonte": "Base de lugares",
   "grupo": "Revisão",
   "icone": "pin",
   "descricao": "Confere coordenadas, área de cobertura, CEP, bairro e rua. Só aponta problemas; nunca inventa endereço.",
   "workflow": "revisao.yml",
   "agenda": "diário, depois das coletas",
   "requer": [],
   "saidas": [
    "data/localizacao.json.gz"
   ]
  },
  {
   "id": "revisor",
   "entradas": {
    "etapa": "score"
   },
   "nome": "Revisor",
   "fonte": "Base de lugares",
   "grupo": "Revisão",
   "icone": "check",
   "descricao": "Dá a cada lugar um score de confiabilidade (0–100) e uma completude, contando só fontes independentes. Lugares duvidosos ficam marcados como não publicáveis.",
   "workflow": "revisao.yml",
   "agenda": "diário, depois das coletas",
   "requer": [],
   "saidas": [
    "data/revisao.json.gz",
    "data/revisao_resumo.json"
   ]
  },
  {
   "id": "cobertura",
   "nome": "Cobertura geográfica",
   "fonte": "Distritos oficiais (GeoSampa)",
   "grupo": "Inteligência",
   "icone": "map",
   "descricao": "Mede a cobertura de cada distrito de São Paulo (quantidade, diversidade, confiabilidade, precisão) e gera a fila de prioridades de coleta. Só recomenda: não dispara outros bots.",
   "workflow": "cobertura.yml",
   "agenda": "diário, depois da revisão",
   "requer": [],
   "saidas": [
    "data/coverage_summary.json",
    "data/coverage_metrics.json.gz",
    "data/coverage_priorities.json.gz"
   ]
  },
  {
   "id": "geo_scanner",
   "parametros_entrada": {
    "distrito": "[0-9]{1,3}",
    "categoria": "[a-z_]{1,40}",
    "max_tarefas": "[0-9]{1,2}"
   },
   "nome": "Geo Scanner",
   "fonte": "OpenStreetMap (Overpass)",
   "grupo": "Inteligência",
   "icone": "pin",
   "descricao": "Pesquisa no OpenStreetMap os distritos e categorias mais prioritários da cobertura e guarda o que achou como descoberta (aguardando validação). Nunca altera os lugares existentes.",
   "workflow": "geo-scanner.yml",
   "agenda": "diário 02:00 (Brasília)",
   "requer": [],
   "saidas": [
    "data/descobertas.json.gz",
    "data/coverage_history.json.gz"
   ]
  },
  {
   "id": "eventos",
   "entradas": {
    "forcar": "true"
   },
   "nome": "Eventos",
   "fonte": "Sites, Ticketmaster e feeds",
   "grupo": "Eventos",
   "icone": "calendar",
   "descricao": "Capta eventos com data, local, preço e foto de todas as fontes cadastradas, tira duplicados e guarda o histórico.",
   "workflow": "eventos.yml",
   "agenda": "a cada 6 horas",
   "requer": [],
   "saidas": [
    "data/eventos_v2.json.gz",
    "data/eventos.json"
   ]
  },
  {
   "id": "turiz_app",
   "nome": "App Turiz",
   "fonte": "Atualização automática",
   "grupo": "Sistema Turiz",
   "icone": "rocket",
   "descricao": "Pega tudo que os bots captaram e atualiza os dados dentro do app Turiz, sem aprovação. Roda numa tarefa agendada do Claude (não no GitHub), por isso o resultado chega como notificação no celular em vez de aparecer aqui em tempo real.",
   "workflow": null,
   "agenda": "todo dia 11:07 (Brasília)",
   "requer": [],
   "saidas": [],
   "externo": true
  }
 ]
};
