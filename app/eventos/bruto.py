"""Formato intermediário (EventoBruto) que todo conector devolve + validação e sanitização de dados externos.

Nada vindo de fora é confiável: texto é limpo de HTML/controles e truncado, URLs só podem ser http(s) sem credenciais,
números e datas passam por limites. Campos que a fonte não informou ficam vazios/None: nunca são preenchidos com suposições.
"""
import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

_TAGS = re.compile(r"<[^>]+>")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SCRIPT = re.compile(r"<(script|style)\b.*?</\1\s*>", re.I | re.S)
LIMITES = {"titulo": 300, "descricao": 5000, "nome": 300, "endereco": 400, "curto": 120, "url": 600, "acessibilidade": 1000}


@dataclass
class ImagemBruta:
    url: str
    largura: int | None = None
    altura: int | None = None
    proporcao: str = ""
    fallback: bool = False
    tipo: str = "principal"        # principal | galeria | artista
    credito: str = ""


@dataclass
class LocalBruto:
    nome: str = ""
    endereco: str = ""
    cidade: str = ""
    estado: str = ""
    pais: str = ""
    cep: str = ""
    lat: float | None = None
    lon: float | None = None
    fonte_id: str = ""             # id do local na fonte, quando existe


@dataclass
class Pessoa:
    nome: str
    fonte_id: str = ""
    url: str = ""
    imagem_url: str = ""
    tipo: str = ""                 # organizador | promotor | produtora | casa


@dataclass
class EventoBruto:
    fonte: str                     # slug da fonte (conector configurado)
    fonte_id: str
    titulo: str
    plataforma: str = ""           # origem dentro da fonte (ex.: ticketmaster | universe | frontgate | tmr)
    descricao: str = ""
    inicio: datetime | None = None
    fim: datetime | None = None
    fuso: str = ""
    data_incerta: bool = False
    local: LocalBruto | None = None
    categorias: list[str] = field(default_factory=list)   # termos como a fonte informou (Music, Rock, MusicEvent...)
    artistas: list[Pessoa] = field(default_factory=list)
    organizador: Pessoa | None = None
    imagens: list[ImagemBruta] = field(default_factory=list)
    classificacao_indicativa: str = ""
    acessibilidade: str = ""
    preco_min: float | None = None
    preco_max: float | None = None
    moeda: str = ""
    gratuito: bool | None = None   # None = a fonte não informou
    status_raw: str = ""
    url: str = ""
    ingresso_url: str = ""
    extra: dict = field(default_factory=dict)


def limpar_texto(s, maximo: int) -> str:
    """Remove scripts/estilos e tags, decodifica entidades, tira caracteres de controle e trunca."""
    if s is None:
        return ""
    s = str(s)
    s = _SCRIPT.sub(" ", s)
    s = _TAGS.sub(" ", s)
    s = html.unescape(s)
    s = _TAGS.sub(" ", s)             # entidades que viram tags (&lt;b&gt;) também saem
    s = _CTRL.sub("", s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s[:maximo]


def url_segura(u, base: str = "") -> str:
    """Só http/https, sem usuário:senha, sem espaços/controles. Vazio se for suspeita."""
    if not u or not isinstance(u, str):
        return ""
    u = _CTRL.sub("", u).strip()
    if u.startswith("//"):
        u = "https:" + u
    elif base and u.startswith("/"):
        p = urlparse(base)
        u = f"{p.scheme}://{p.netloc}{u}"
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.netloc or p.username or p.password or len(u) > LIMITES["url"] or re.search(r"\s", u):
        return ""
    return u


def _num(x, minimo=None, maximo=None):
    try:
        v = float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    if (minimo is not None and v < minimo) or (maximo is not None and v > maximo):
        return None
    return v


def _inteiro(x):
    v = _num(x, 1, 20000)
    return int(v) if v else None


def _utc(d):
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def validar(e: EventoBruto):
    """-> (EventoBruto limpo, "") ou (None, motivo do descarte)."""
    if not (e.fonte and str(e.fonte_id).strip()):
        return None, "sem identificador externo"
    e.fonte_id = limpar_texto(e.fonte_id, 200)
    e.titulo = limpar_texto(e.titulo, LIMITES["titulo"])
    if len(e.titulo) < 2:
        return None, "sem título"
    e.descricao = limpar_texto(e.descricao, LIMITES["descricao"])
    e.inicio, e.fim = _utc(e.inicio), _utc(e.fim)
    for d in (e.inicio, e.fim):
        if d and not (2000 <= d.year <= 2100):
            return None, "data fora do intervalo plausível"
    if e.fim and e.inicio and e.fim < e.inicio:
        e.fim = None                                            # fim anterior ao início: informação inconsistente, descarta só o fim
    if e.inicio is None and not e.data_incerta:
        return None, "sem data"
    e.fuso = limpar_texto(e.fuso, 60)
    e.plataforma = limpar_texto(e.plataforma, 60).lower()
    e.url, e.ingresso_url = url_segura(e.url), url_segura(e.ingresso_url)
    e.preco_min, e.preco_max = _num(e.preco_min, 0, 1_000_000), _num(e.preco_max, 0, 1_000_000)
    if e.preco_min is not None and e.preco_max is not None and e.preco_max < e.preco_min:
        e.preco_min, e.preco_max = e.preco_max, e.preco_min
    e.moeda = limpar_texto(e.moeda, 8).upper()
    e.classificacao_indicativa = limpar_texto(e.classificacao_indicativa, 40)
    e.acessibilidade = limpar_texto(e.acessibilidade, LIMITES["acessibilidade"])
    e.status_raw = limpar_texto(e.status_raw, 60)
    e.categorias = [c for c in (limpar_texto(c, LIMITES["curto"]) for c in e.categorias) if c]
    if e.local:
        L = e.local
        L.nome, L.endereco = limpar_texto(L.nome, LIMITES["nome"]), limpar_texto(L.endereco, LIMITES["endereco"])
        L.cidade, L.estado, L.pais = (limpar_texto(x, LIMITES["curto"]) for x in (L.cidade, L.estado, L.pais))
        L.cep, L.fonte_id = limpar_texto(L.cep, 20), limpar_texto(L.fonte_id, 200)
        L.lat, L.lon = _num(L.lat, -90, 90), _num(L.lon, -180, 180)
        if (L.lat is None) != (L.lon is None) or (L.lat == 0 and L.lon == 0):
            L.lat = L.lon = None                                # coordenada incompleta ou "ilha nula": não confiável
    imgs = []
    for i in e.imagens:
        u = url_segura(i.url)
        if u:
            i.url = u
            i.largura, i.altura = _inteiro(i.largura), _inteiro(i.altura)
            i.proporcao, i.credito = limpar_texto(i.proporcao, 10), limpar_texto(i.credito, 200)
            imgs.append(i)
    e.imagens = imgs
    e.artistas = [Pessoa(nome=n, fonte_id=limpar_texto(a.fonte_id, 200), url=url_segura(a.url), imagem_url=url_segura(a.imagem_url))
                  for a in e.artistas if (n := limpar_texto(a.nome, LIMITES["nome"]))]
    if e.organizador:
        n = limpar_texto(e.organizador.nome, LIMITES["nome"])
        e.organizador = Pessoa(nome=n, fonte_id=limpar_texto(e.organizador.fonte_id, 200), url=url_segura(e.organizador.url), tipo=e.organizador.tipo) if n else None
    return e, ""
