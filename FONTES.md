# Diagnóstico de fontes

Gerado em 2026-11-13 17:54 (UTC) pelo GitHub Actions. Resultado de acesso por robô; a decisão de usar cada fonte ainda depende dos termos de uso do site.

| Fonte | Categoria | Resultado | HTTP | Eventos JSON-LD | Observação |
|---|---|---|---|---|---|
| [meetup](https://www.meetup.com/find/?location=br--S%C3%A3o+Paulo) | evento | Dá para coletar (JSON-LD) | 200 | 11 | API só com OAuth |
| [ticket360](https://www.ticket360.com.br/) | evento | Dá para coletar seguindo os links dos eventos (modo listagem) | 200 | 0 (nos detalhes: 5/5) | shows e festas |
| [visite_sp](https://www.visitesaopaulo.com/) | evento | Dá para coletar seguindo os links dos eventos (modo listagem) | 200 | 0 (nos detalhes: 4/4) | SPTuris, agenda da cidade |
| [brasilapi_cep](https://brasilapi.com.br/api/cep/v2/01001000) | dados_abertos | Acessível | 200 | - | CEP -> coordenadas |
| [cnpj_brasilapi](https://brasilapi.com.br/api/cnpj/v1/00000000000191) | dados_abertos | Acessível | 200 | - | consulta de um CNPJ por vez |
| [commons](https://commons.wikimedia.org/w/api.php?action=query&meta=siteinfo&format=json) | imagem | Acessível | 200 | - | fotos com licença livre |
| [geofabrik_sp](https://download.geofabrik.de/south-america/brazil/sudeste.html) | lugar | Acessível | 200 | - | extrato OSM completo (alternativa ao Overpass) |
| [nominatim](https://nominatim.openstreetmap.org/status.php?format=json) | lugar | Acessível | 200 | - | endereços (1 req/s) |
| [sp_dados_abertos](https://dados.prefeitura.sp.gov.br/api/3/action/package_list) | dados_abertos | Acessível | 200 | - | CKAN da Prefeitura de SP |
| [wikidata](https://query.wikidata.org/sparql?query=SELECT%20%3Fs%20WHERE%20%7B%3Fs%20%3Fp%20%3Fo%7D%20LIMIT%201&format=json) | lugar | Acessível | 200 | - | ligações com wikidata/P18 |
| [anotaai](https://anota.ai/) | cardapio | Abre, mas sem dados estruturados (precisa de link/seletor) | 200 | 0 | plataforma de cardápio digital |
| [bilheteria_digital](https://www.bilheteriadigital.com/) | evento | Abre, mas sem dados estruturados (precisa de link/seletor) | 200 | 0 | shows e festas |
| [goomer](https://goomer.app/) | cardapio | Abre, mas sem dados estruturados (precisa de link/seletor) | 200 | 0 | plataforma de cardápio digital |
| [guia_folha](https://guia.folha.uol.com.br/) | evento | Abre, mas sem dados estruturados (precisa de link/seletor) | 200 | 0 (nos detalhes: 0/4) | guia |
| [ingresso_com](https://www.ingresso.com/) | evento | Abre, mas sem dados estruturados (precisa de link/seletor) | 200 | 0 | cinema/teatro |
| [prefeitura_agenda](https://www.prefeitura.sp.gov.br/cidade/secretarias/cultura/) | evento | Abre, mas sem dados estruturados (precisa de link/seletor) | 200 | 0 | Secretaria Municipal de Cultura |
| [theatro_municipal](https://theatromunicipal.org.br/) | evento | Abre, mas sem dados estruturados (precisa de link/seletor) | 200 | 0 | Theatro Municipal |
| [timeout_sp](https://www.timeout.com/sao-paulo) | evento | Abre, mas sem dados estruturados (precisa de link/seletor) | 200 | 0 | guia |
| [veja_sp](https://vejasp.abril.com.br/) | evento | Abre, mas sem dados estruturados (precisa de link/seletor) | 200 | 0 | guia |
| [bandsintown_api](https://rest.bandsintown.com/artists/Coldplay?app_id=turiz) | evento | Funciona com chave de API | 403 | - | exige app_id aprovado |
| [foursquare_api](https://places-api.foursquare.com/places/search?query=pizza&near=Sao%20Paulo) | avaliacao | Funciona com chave de API | 400 | - | API oficial, exige chave |
| [google_places_api](https://places.googleapis.com/v1/places:searchText) | avaliacao | Funciona com chave de API | 403 | - | API oficial paga (coletor google já existe) |
| [ticketmaster_api](https://app.ticketmaster.com/discovery/v2/events.json?countryCode=BR&size=1) | evento | Funciona com chave de API | 401 | - | API oficial (chave gratuita) |
| [tomtom_api](https://api.tomtom.com/search/2/poiSearch/pizza.json?lat=-23.55&lon=-46.63) | lugar | Funciona com chave de API | 401 | - | POIs, exige chave |
| [tripadvisor_api](https://api.content.tripadvisor.com/api/v1/location/search?searchQuery=pizza) | avaliacao | Funciona com chave de API | 401 | - | API oficial, exige chave |
| [sympla](https://www.sympla.com.br/eventos/sao-paulo-sp) | evento | robots.txt proíbe | 200 | 0 | sem API pública de busca |
| [cnpj_receita_novo](https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/) | dados_abertos | erro 404 | 404 | - | novo endereço dos mesmos dados |
| [eventbrite](https://www.eventbrite.com.br/d/brazil--s%C3%A3o-paulo/events/) | evento | Bloqueia robôs | 405 | 0 | sem busca pública pela API |
| [guia_da_semana](https://www.guiadasemana.com.br/sao-paulo) | evento | Bloqueia robôs | 403 | 0 | guia |
| [ifood](https://www.ifood.com.br/restaurantes) | cardapio | Bloqueia robôs | 403 | 0 | não raspamos: só guardamos o link informado pelo restaurante |
| [menudino](https://www.menudino.com/) | cardapio | Bloqueia robôs | 403 | 0 | plataforma de cardápio digital |
| [sescsp](https://www.sescsp.org.br/programacao/) | evento | Bloqueia robôs | 403 | 0 | programação do Sesc SP |
| [cnpj_receita](https://dadosabertos.rfb.gov.br/CNPJ/) | dados_abertos | Sem resposta | - | - | estabelecimentos CNAE 5611 (restaurantes/bares): ampliaria a base |
| [overpass](https://overpass-api.de/api/status) | lugar | Sem resposta | - | - | restaurantes e bares do OSM |
