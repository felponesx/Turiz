"""Categorias do TURIZ para eventos (3 grupos, com subcategorias e gêneros) e regras de classificação.

Um evento pode ter várias categorias. As regras usam, nesta ordem: termos de classificação da fonte (segmento/gênero do
Ticketmaster, tipo schema.org) e palavras-chave do título/descrição em português e inglês.
"""
import re
from .normalizar import norm_texto

G_MUSICA, G_GASTRO, G_CULTURA = "musica_entretenimento", "gastronomia", "cultura_lazer"

# (slug, nome, grupo, slug do pai ou None)
CATEGORIAS = [
    ("musica-entretenimento", "Música e entretenimento", G_MUSICA, None),
    ("shows", "Shows", G_MUSICA, "musica-entretenimento"),
    ("festivais", "Festivais", G_MUSICA, "musica-entretenimento"),
    ("musica-ao-vivo", "Música ao vivo", G_MUSICA, "musica-entretenimento"),
    ("concertos", "Concertos", G_MUSICA, "musica-entretenimento"),
    ("festas", "Festas", G_MUSICA, "musica-entretenimento"),
    ("baladas", "Baladas", G_MUSICA, "musica-entretenimento"),
    ("djs", "DJs", G_MUSICA, "musica-entretenimento"),
    ("rock", "Rock", G_MUSICA, "shows"), ("pop", "Pop", G_MUSICA, "shows"), ("sertanejo", "Sertanejo", G_MUSICA, "shows"),
    ("samba-pagode", "Samba e pagode", G_MUSICA, "shows"), ("funk", "Funk", G_MUSICA, "shows"),
    ("eletronica", "Música eletrônica", G_MUSICA, "shows"), ("hip-hop", "Hip hop e rap", G_MUSICA, "shows"),
    ("jazz-blues", "Jazz e blues", G_MUSICA, "shows"), ("mpb", "MPB", G_MUSICA, "shows"), ("forro", "Forró", G_MUSICA, "shows"),
    ("reggae", "Reggae", G_MUSICA, "shows"), ("metal", "Metal", G_MUSICA, "shows"), ("classica", "Música clássica", G_MUSICA, "concertos"),
    ("gastronomia", "Gastronomia", G_GASTRO, None),
    ("festivais-gastronomicos", "Festivais gastronômicos", G_GASTRO, "gastronomia"),
    ("feiras-de-comida", "Feiras de comida", G_GASTRO, "gastronomia"),
    ("experiencias-culinarias", "Experiências culinárias", G_GASTRO, "gastronomia"),
    ("degustacoes", "Degustações", G_GASTRO, "gastronomia"),
    ("eventos-em-restaurantes", "Eventos em restaurantes", G_GASTRO, "gastronomia"),
    ("eventos-em-bares", "Eventos em bares", G_GASTRO, "gastronomia"),
    ("experiencias-exclusivas", "Experiências exclusivas", G_GASTRO, "gastronomia"),
    ("cultura-lazer", "Cultura e lazer", G_CULTURA, None),
    ("exposicoes", "Exposições", G_CULTURA, "cultura-lazer"),
    ("feiras", "Feiras", G_CULTURA, "cultura-lazer"),
    ("eventos-culturais", "Eventos culturais", G_CULTURA, "cultura-lazer"),
    ("cinema", "Cinema", G_CULTURA, "cultura-lazer"),
    ("teatro", "Teatro", G_CULTURA, "cultura-lazer"),
    ("comedia", "Comédia e stand-up", G_CULTURA, "teatro"),
    ("experiencias-tematicas", "Experiências temáticas", G_CULTURA, "cultura-lazer"),
]
PAI = {slug: pai for slug, _, _, pai in CATEGORIAS}
GRUPO = {slug: g for slug, _, g, _ in CATEGORIAS}

# termos da fonte (já normalizados) -> categorias
TERMOS_FONTE = {
    "music": ["shows"], "musicevent": ["shows"], "concert": ["shows"], "festival": ["festivais"],
    "rock": ["rock"], "alternative": ["rock"], "pop": ["pop"], "country": ["sertanejo"], "latin": ["shows"], "dance electronic": ["eletronica"],
    "hip hop rap": ["hip-hop"], "r b": ["shows"], "jazz": ["jazz-blues"], "blues": ["jazz-blues"], "classical": ["concertos", "classica"],
    "metal": ["metal"], "reggae": ["reggae"], "world": ["shows"], "folk": ["shows"],
    "arts theatre": ["teatro"], "theatreevent": ["teatro"], "comedyevent": ["comedia"], "comedy": ["comedia"], "theatre": ["teatro"], "theater": ["teatro"],
    "film": ["cinema"], "screeningevent": ["cinema"], "exhibitionevent": ["exposicoes"], "foodevent": ["experiencias-culinarias"],
    "socialevent": ["festas"], "danceevent": ["festas"], "miscellaneous": [],
    "musica": ["shows"], "teatro": ["teatro"], "cinema": ["cinema"], "exposicao": ["exposicoes"], "gastronomia": ["experiencias-culinarias"],
    "festa": ["festas"], "evento": [],
}
# palavras-chave (regex sobre texto normalizado) -> categorias
PALAVRAS = [
    (r"\b(festival|festa|feira|food|noite) (gastronomic\w*|do (churrasco|vinho|chocolate|hamburguer|cafe)|de (comida|rua))\b", ["festivais-gastronomicos"]),
    (r"\b(food ?truck|feira (gastronomica|de comida|de rua)|feira do (prato|sabor))\b", ["feiras-de-comida"]),
    (r"\b(degusta\w*|harmoniza\w*|wine|vinhos?|cervejas? artesana\w*|whisk\w*|cachaca)\b", ["degustacoes"]),
    (r"\b(jantar|brunch|menu degustacao|aula (aberta )?(com o )?chef|culinari\w*|masterclass|workshop de (culinaria|cozinha))\b", ["experiencias-culinarias"]),
    (r"\b(experiencia exclusiva|chef.s table|mesa do chef|menu exclusivo)\b", ["experiencias-exclusivas"]),
    (r"\bfestival\b", ["festivais"]),
    (r"\b(show|turne|tour|apresenta|ao vivo)\b", ["shows"]), (r"\b(musica ao vivo|roda de (samba|choro)|acustico|live music)\b", ["musica-ao-vivo"]),
    (r"\b(orquestra|sinfonic\w*|concerto|filarmonic\w*|recital)\b", ["concertos"]),
    (r"\b(balada|club|after party|baile)\b", ["baladas"]), (r"\b(festa|party|happy hour|karaoke|carnaval|pre carnaval)\b", ["festas"]),
    (r"\bdj(s| set)?\b", ["djs"]), (r"\b(rock|punk|hardcore|indie)\b", ["rock"]), (r"\b(sertanej\w*|modao|rodeio)\b", ["sertanejo"]),
    (r"\b(samba|pagode|choro|roda de samba)\b", ["samba-pagode"]), (r"\b(funk|baile funk)\b", ["funk"]),
    (r"\b(eletronic\w*|techno|house music|trance|edm)\b", ["eletronica"]), (r"\b(rap|hip ?hop|trap)\b", ["hip-hop"]),
    (r"\b(jazz|blues|bossa nova)\b", ["jazz-blues"]), (r"\b(mpb|caetano|gilberto gil|chico buarque|bossa)\b", ["mpb"]),
    (r"\b(forro|xote|baiao)\b", ["forro"]), (r"\b(reggae|ska)\b", ["reggae"]), (r"\b(metal|trash|thrash)\b", ["metal"]),
    (r"\b(exposicao|mostra|galeria|museu|vernissage|instalacao)\b", ["exposicoes"]), (r"\bfeira\b", ["feiras"]),
    (r"\b(cinema|filme|sessao|cine ?clube|pre ?estreia|mostra de cinema)\b", ["cinema"]),
    (r"\b(teatro|peca|espetaculo|musical|monologo|infantil)\b", ["teatro"]), (r"\b(stand ?up|comedia|humor|improviso)\b", ["comedia"]),
    (r"\b(cultural|cultura|literari\w*|bienal|saraus?|oficina)\b", ["eventos-culturais"]), (r"\b(tematic\w*|imersiv\w*|escape room|experiencia imersiva)\b", ["experiencias-tematicas"]),
]


def classificar(titulo: str, descricao: str, termos: list[str], tipo_lugar: str = "") -> list[tuple[str, bool, str]]:
    """-> [(slug, primaria, origem)]. `tipo_lugar`: 'restaurante' | 'bar' quando o local é um lugar do TURIZ."""
    achados: list[tuple[str, str]] = []
    for t in termos:
        for slug in TERMOS_FONTE.get(norm_texto(t), []):
            achados.append((slug, "fonte"))
    texto = norm_texto(f"{titulo} {descricao[:600]}")
    for rx, slugs in PALAVRAS:
        if re.search(rx, texto):
            achados += [(s, "regra") for s in slugs]
    if tipo_lugar == "restaurante":
        achados.append(("eventos-em-restaurantes", "regra"))
    elif tipo_lugar == "bar":
        achados.append(("eventos-em-bares", "regra"))
    visto, saida = set(), []
    for slug, origem in achados:
        if slug not in visto:
            visto.add(slug)
            saida.append((slug, origem))
    # "música ao vivo" em restaurante/bar: soma a categoria de música quando já é show/acústico
    if tipo_lugar and any(s in visto for s in ("shows", "musica-ao-vivo")) and "musica-ao-vivo" not in visto:
        saida.append(("musica-ao-vivo", "regra"))
    # festival gastronômico não deve virar só "festivais"
    return [(s, i == 0, o) for i, (s, o) in enumerate(saida)]


def com_ancestrais(slugs):
    """Inclui os pais de cada categoria (para filtrar por grupo/categoria-mãe)."""
    out = []
    for s in slugs:
        while s and s not in out:
            out.append(s)
            s = PAI.get(s)
    return out


def filhas_de(slug: str) -> set[str]:
    """O slug e todas as categorias descendentes (filtro por categoria inclui subcategorias)."""
    r, mudou = {slug}, True
    while mudou:
        mudou = False
        for s, p in PAI.items():
            if p in r and s not in r:
                r.add(s)
                mudou = True
    return r
