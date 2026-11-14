"""Busca em linguagem natural (pt-BR) -> Filtros. Ex.: "shows hoje em São Paulo", "restaurantes com música ao vivo",
"festas neste fim de semana", "eventos gratuitos amanhã", "festival gastronômico até R$ 100".
Só interpreta o que reconhece; o resto vira busca por texto. Nunca devolve evento vencido como futuro (a consulta já os filtra)."""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import taxonomia
from .consulta import Filtros
from .modelos import EventoLocal
from .normalizar import norm_texto

TZ = ZoneInfo("America/Sao_Paulo")
MESES = {m: i + 1 for i, m in enumerate(["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"])}
DIAS_SEMANA = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}
UFS = {"sp": "SP", "rj": "RJ", "mg": "MG", "ba": "BA", "pr": "PR", "rs": "RS", "sc": "SC", "df": "DF", "go": "GO", "pe": "PE", "ce": "CE", "es": "ES"}
PARADA = set("a o as os de da do das dos em no na nos nas para pra por com sem um uma uns umas e ou que perto proximo proximos proxima proximas "
             "quero ver tem tudo todos todas onde ha existe mostrar mostre busque buscar procurar procuro evento eventos".split())
# palavras que definem categoria (além das regras da taxonomia)
CAT_PALAVRAS = {"show": "shows", "shows": "shows", "festival": "festivais", "festivais": "festivais", "festa": "festas", "festas": "festas", "balada": "baladas", "baladas": "baladas",
                "dj": "djs", "djs": "djs", "teatro": "teatro", "peca": "teatro", "stand up": "comedia", "comedia": "comedia", "exposicao": "exposicoes", "exposicoes": "exposicoes",
                "cinema": "cinema", "degustacao": "degustacoes", "degustacoes": "degustacoes", "gastronomia": "gastronomia", "gastronomico": "gastronomia", "gastronomicos": "gastronomia",
                "sertanejo": "sertanejo", "samba": "samba-pagode", "pagode": "samba-pagode", "rock": "rock", "jazz": "jazz-blues", "forro": "forro", "funk": "funk", "mpb": "mpb",
                "musica ao vivo": "musica-ao-vivo", "ao vivo": "musica-ao-vivo", "feira": "feiras", "feiras": "feiras", "cultura": "cultura-lazer", "cultural": "eventos-culturais", "musica": "musica-entretenimento"}


def _dia(d: datetime):
    ini = d.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return ini.astimezone(timezone.utc), (ini + timedelta(days=1)).astimezone(timezone.utc)


def _quando(t: str, agora: datetime):
    """-> (data_de, data_ate, trecho_consumido, rotulo) ou None."""
    hoje = agora.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    u = lambda d: d.astimezone(timezone.utc)
    if re.search(r"\bhoje\b|\besta noite\b|\bhoje a noite\b", t):
        a, b = _dia(hoje)
        return agora if a < agora < b else a, b, re.search(r"\bhoje( a noite)?\b|\besta noite\b", t).group(0), "hoje"
    if re.search(r"\bamanha\b", t):
        a, b = _dia(hoje + timedelta(days=1))
        return a, b, "amanha", "amanhã"
    m = re.search(r"\b(fim|final) de semana\b|\bfds\b", t)
    if m:
        dias = (5 - hoje.weekday()) % 7 if hoje.weekday() != 6 else -1       # sábado mais próximo (no domingo: o próprio fim de semana)
        sab = hoje + timedelta(days=dias if dias >= 0 else -1)
        if re.search(r"\b(que vem|proximo)\b", t):
            sab += timedelta(days=7)
        ini = max(u(sab), agora) if u(sab) < agora < u(sab + timedelta(days=2)) else u(sab)
        return ini, u(sab + timedelta(days=2)), m.group(0), "fim de semana"
    if re.search(r"\bsemana que vem\b|\bproxima semana\b", t):
        seg = hoje + timedelta(days=7 - hoje.weekday())
        return u(seg), u(seg + timedelta(days=7)), "semana que vem" if "semana que vem" in t else "proxima semana", "semana que vem"
    if re.search(r"\b(esta|essa) semana\b", t):
        return agora, u(hoje + timedelta(days=7 - hoje.weekday())), re.search(r"\b(esta|essa) semana\b", t).group(0), "esta semana"
    if re.search(r"\bmes que vem\b|\bproximo mes\b", t):
        p = (hoje.replace(day=1) + timedelta(days=32)).replace(day=1)
        q = (p + timedelta(days=32)).replace(day=1)
        return u(p), u(q), "mes que vem" if "mes que vem" in t else "proximo mes", "mês que vem"
    if re.search(r"\b(este|esse|neste|nesse) mes\b", t):
        q = (hoje.replace(day=1) + timedelta(days=32)).replace(day=1)
        return agora, u(q), re.search(r"\b(este|esse|neste|nesse) mes\b", t).group(0), "este mês"
    m = re.search(r"\b(?:dia )?(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        try:
            ano = int(m.group(3)) + (2000 if m.group(3) and len(m.group(3)) == 2 else 0) if m.group(3) else hoje.year
            d = hoje.replace(year=ano, month=int(m.group(2)), day=int(m.group(1)))
            if not m.group(3) and d < hoje:
                d = d.replace(year=ano + 1)
            a, b = _dia(d)
            return a, b, m.group(0), d.strftime("%d/%m/%Y")
        except ValueError:
            pass
    m = re.search(r"\bdia (\d{1,2})(?: de (" + "|".join(MESES) + r"))?\b", t)
    if m:
        mes = MESES[m.group(2)] if m.group(2) else hoje.month
        try:
            d = hoje.replace(month=mes, day=int(m.group(1)))
            if d < hoje:
                d = d.replace(year=d.year + 1) if m.group(2) else (hoje.replace(day=1) + timedelta(days=32)).replace(day=int(m.group(1)))
            a, b = _dia(d)
            return a, b, m.group(0), d.strftime("%d/%m/%Y")
        except ValueError:
            pass
    m = re.search(r"\b(?:em |no mes de |de )?(" + "|".join(MESES) + r")\b", t)
    if m:
        mes = MESES[m.group(1)]
        ano = hoje.year + (1 if mes < hoje.month else 0)
        ini = hoje.replace(year=ano, month=mes, day=1)
        fim = (ini + timedelta(days=32)).replace(day=1)
        return max(u(ini), agora), u(fim), m.group(0), m.group(1)
    m = re.search(r"\b(?:no |neste |nesta |na )?(segunda|terca|quarta|quinta|sexta|sabado|domingo)\b", t)
    if m:
        alvo = DIAS_SEMANA[m.group(1)]
        d = hoje + timedelta(days=(alvo - hoje.weekday()) % 7)
        a, b = _dia(d)
        return max(a, agora), b, m.group(0), m.group(1)
    return None


def interpretar(db: Session, texto: str, agora: datetime | None = None) -> tuple[Filtros, dict]:
    agora = agora or datetime.now(timezone.utc)
    t = " " + norm_texto(texto) + " "
    t = re.sub(r"\s+", " ", t)
    f, info = Filtros(), {"texto": texto}
    # preço
    if re.search(r"\b(gratis|gratuito|gratuitos|gratuita|gratuitas|de graca|free|sem custo)\b", t):
        f.gratuito = True
        info["gratuito"] = True
        t = re.sub(r"\b(gratis|gratuito|gratuitos|gratuita|gratuitas|de graca|free|sem custo)\b", " ", t)
    m = re.search(r"\b(?:ate|abaixo de|menos de|no maximo|maximo)\s*(?:r\$?\s*)?(\d+(?:[.,]\d+)?)\b", t)
    if m:
        f.preco_max = float(m.group(1).replace(",", "."))
        info["preco_max"] = f.preco_max
        t = t.replace(m.group(0), " ")
    # onde
    cidades = {norm_texto(c): c for c in db.scalars(select(EventoLocal.cidade).distinct()) if c}
    achada = None
    for nome in sorted(cidades, key=len, reverse=True):          # nomes longos primeiro ("rio de janeiro" antes de "rio")
        if re.search(rf"\b(?:em|na|no|de|perto de|proximo a|aqui em)\s+{re.escape(nome)}\b|\b{re.escape(nome)}\b", t):
            achada = nome
            break
    if achada:
        f.cidade = cidades[achada]
        info["cidade"] = f.cidade
        t = re.sub(rf"\b(?:em|na|no|de|perto de|proximo a|aqui em)\s+{re.escape(achada)}\b|\b{re.escape(achada)}\b", " ", t, count=1)
    else:
        m = re.search(r"\b(?:em|no|na)\s+(sp|rj|mg|ba|pr|rs|sc|df|go|pe|ce|es)\b", t)
        if m:
            f.estado = UFS[m.group(1)]
            info["estado"] = f.estado
            t = t.replace(m.group(0), " ", 1)
    if re.search(r"\bno brasil\b|\bbrasil\b", t):
        f.pais = "BR"
        info["pais"] = "BR"
        t = re.sub(r"\bno brasil\b|\bbrasil\b", " ", t)
    # quando
    q = _quando(t, agora)
    if q:
        f.data_de, f.data_ate = q[0], q[1]
        info["quando"] = q[3]
        t = t.replace(q[2], " ", 1)
    # tipo de estabelecimento
    for pal, tipo in (("restaurantes", "restaurante"), ("restaurante", "restaurante"), ("bares", "bar"), ("bar", "bar")):
        if re.search(rf"\b{pal}\b", t):
            f.tipo_local = tipo
            info["tipo_local"] = tipo
            t = re.sub(rf"\b{pal}\b", " ", t, count=1)
            break
    # categoria
    for frase in sorted(CAT_PALAVRAS, key=len, reverse=True):
        if re.search(rf"\b{frase}\b", t):
            f.categoria = CAT_PALAVRAS[frase]
            info["categoria"] = f.categoria
            t = re.sub(rf"\b{frase}\b", " ", t, count=1)
            break
    if not f.categoria:
        c = taxonomia.classificar(texto, "", [])
        if c:
            f.categoria, info["categoria"] = c[0][0], c[0][0]
    # o que sobrou vira texto livre (nomes de artistas, locais, eventos)
    sobra = [w for w in t.split() if w not in PARADA and len(w) > 1]
    if sobra:
        f.q = " ".join(sobra)
        info["texto_livre"] = f.q
    return f, info
