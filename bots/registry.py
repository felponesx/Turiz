"""Registro dos bots exibidos no painel. A ordem aqui é a ordem na tela.
`python -m bots.registry > painel/bots.json` regenera o arquivo lido pelo painel (um teste garante que está em dia)."""
import json
import sys

GRUPOS = ["Lugares", "Enriquecimento", "Eventos", "Sistema Turiz"]

BOTS = [
    {"id": "osm", "encadeia": True, "entradas": {"fontes": "osm"}, "nome": "Restaurantes e bares", "fonte": "OpenStreetMap", "grupo": "Lugares", "icone": "pin",
     "descricao": "Varre São Paulo em regiões e capta restaurantes, lanchonetes, cafés e bares com nome, endereço, telefone, site e horário.",
     "workflow": "coleta.yml", "agenda": "segunda 03:00 (Brasília)", "requer": [], "saidas": ["data/lugares.json"]},
    {"id": "receita", "nome": "Lugares da Receita Federal", "fonte": "Receita + IBGE (dados abertos)", "grupo": "Lugares", "icone": "building",
     "descricao": "Amplia a base com bares e restaurantes ativos em São Paulo (sem CNPJ, sem MEI) e coordenadas do IBGE.",
     "workflow": "receita.yml", "agenda": "dia 20 de cada mês", "requer": [], "saidas": ["data/lugares_receita.json.gz"]},
    {"id": "sites", "encadeia": True, "entradas": {"fontes": "sites"}, "nome": "Lugares em sites", "fonte": "Sites (JSON-LD)", "grupo": "Lugares", "icone": "globe",
     "descricao": "Lê dados estruturados de restaurantes e bares publicados em sites listados em sources.yml.",
     "workflow": "coleta.yml", "agenda": "junto com a coleta semanal", "requer": [], "saidas": ["data/lugares.json"]},
    {"id": "google", "nome": "Google Places", "fonte": "Google Places API", "grupo": "Lugares", "icone": "star",
     "descricao": "Capta lugares com nota e número de avaliações. Só roda com a chave GOOGLE_PLACES_API_KEY (Places API ativada e faturamento).",
     "workflow": "google.yml", "agenda": "segunda, depois da coleta", "requer": ["GOOGLE_PLACES_API_KEY"], "saidas": ["data/lugares.json"]},
    {"id": "enderecos", "encadeia": True, "nome": "Endereços", "fonte": "Nominatim (OpenStreetMap)", "grupo": "Enriquecimento", "icone": "map",
     "descricao": "Completa bairro, CEP e rua pelas coordenadas. Nunca inventa número de casa.",
     "workflow": "enderecos.yml", "agenda": "depois da coleta semanal", "requer": [], "saidas": ["data/lugares.json"]},
    {"id": "imagens", "encadeia": True, "nome": "Imagens dos lugares", "fonte": "Wikimedia Commons + sites", "grupo": "Enriquecimento", "icone": "image",
     "descricao": "Reúne referências de fotos (link, autor, licença) do Commons e da imagem de capa do site de cada lugar.",
     "workflow": "imagens.yml", "agenda": "depois dos endereços", "requer": [], "saidas": ["data/imagens.json"]},
    {"id": "instagram", "encadeia": True, "nome": "Redes sociais", "fonte": "Sites e OpenStreetMap", "grupo": "Enriquecimento", "icone": "share",
     "descricao": "Liga cada lugar ao perfil de Instagram (e outras redes) publicado pelo próprio lugar. Não raspa redes sociais.",
     "workflow": "instagram.yml", "agenda": "depois das imagens", "requer": [], "saidas": ["data/redes_sociais.json"]},
    {"id": "cardapios", "encadeia": True, "nome": "Cardápios", "fonte": "Sites dos lugares", "grupo": "Enriquecimento", "icone": "menu",
     "descricao": "Acha o cardápio oficial no site de cada lugar (itens e preços quando o site publica).",
     "workflow": "cardapios.yml", "agenda": "depois das redes sociais", "requer": [], "saidas": ["data/cardapios.json"]},
    {"id": "fotos", "encadeia": True, "nome": "Fotos (miniaturas)", "fonte": "Imagens captadas", "grupo": "Enriquecimento", "icone": "photo",
     "descricao": "Baixa e reduz as fotos de lugares e eventos para o app não depender do site de origem.",
     "workflow": "fotos.yml", "agenda": "depois dos cardápios", "requer": [], "saidas": ["data/fotos/"]},
    {"id": "fotos_exemplo", "nome": "Fotos ilustrativas", "fonte": "Wikimedia Commons", "grupo": "Enriquecimento", "icone": "photo",
     "descricao": "Fotos de licença livre por tema (pizza, show, bar...) para lugares e eventos sem foto própria.",
     "workflow": "fotos-exemplo.yml", "agenda": "sob demanda", "requer": [], "saidas": ["data/fotos_exemplo/"]},
    {"id": "eventos", "entradas": {"forcar": "true"}, "nome": "Eventos", "fonte": "Sites, Ticketmaster e feeds", "grupo": "Eventos", "icone": "calendar",
     "descricao": "Capta eventos com data, local, preço e foto de todas as fontes cadastradas, tira duplicados e guarda o histórico.",
     "workflow": "eventos.yml", "agenda": "a cada 6 horas", "requer": [], "saidas": ["data/eventos_v2.json.gz", "data/eventos.json"]},
    {"id": "turiz_app", "nome": "App Turiz", "fonte": "Atualização automática", "grupo": "Sistema Turiz", "icone": "rocket",
     "descricao": "Pega tudo que os bots captaram e atualiza os dados dentro do app Turiz, sem aprovação. Roda numa tarefa agendada do Claude (não no GitHub), por isso o resultado chega como notificação no celular em vez de aparecer aqui em tempo real.",
     "workflow": None, "agenda": "todo dia 11:07 (Brasília)", "requer": [], "saidas": [], "externo": True},
]


def por_id(bot_id):
    return next((b for b in BOTS if b["id"] == bot_id), None)


def como_json():
    return json.dumps({"grupos": GRUPOS, "bots": BOTS}, ensure_ascii=False, indent=1)


def como_js():
    """Mesmo conteúdo em <script>: funciona até quando o painel é aberto como arquivo local (file://)."""
    return "window.BOTS_REGISTRY = " + como_json() + ";\n"


if __name__ == "__main__":
    sys.stdout.write(como_js() if "--js" in sys.argv else como_json() + "\n")
