"""Utilitários dos conectores genéricos: mapeamento de campos configurável -> EventoBruto."""
import csv
import hashlib
import io
from datetime import datetime, timezone
from ..bruto import EventoBruto, ImagemBruta, LocalBruto, Pessoa


def caminho(obj, path: str):
    """Valor em 'a.b.0.c' (dict/list). None se não existir."""
    for p in (path or "").split("."):
        if p == "":
            continue
        if isinstance(obj, dict):
            obj = obj.get(p)
        elif isinstance(obj, list) and p.isdigit() and int(p) < len(obj):
            obj = obj[int(p)]
        else:
            return None
        if obj is None:
            return None
    return obj


def parse_data(v, fuso_padrao="America/Sao_Paulo"):
    """ISO 8601, 'dd/mm/aaaa [hh:mm]' ou epoch. Sem fuso -> fuso_padrao. None se não entender."""
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    s = str(v).strip()
    d = None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        for f in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d %H:%M", "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
            try:
                d = datetime.strptime(s, f)
                break
            except ValueError:
                continue
    if d is None:
        return None
    if d.tzinfo is None:
        from zoneinfo import ZoneInfo
        d = d.replace(tzinfo=ZoneInfo(fuso_padrao))
    return d


def _f(x):
    try:
        return float(str(x).replace(",", ".")) if x not in (None, "") else None
    except ValueError:
        return None


def _lista(v):
    if v in (None, ""):
        return []
    if isinstance(v, list):
        return [x for x in v if x]
    return [x.strip() for x in str(v).replace(";", ",").split(",") if x.strip()]


def de_mapa(item: dict, mapa: dict, fonte: str, padroes: dict | None = None) -> EventoBruto | None:
    """item (JSON/linha) + mapa {campo_turiz: caminho} -> EventoBruto. `padroes`: valores fixos (cidade, pais, organizador...)."""
    g = lambda k: caminho(item, mapa[k]) if mapa.get(k) else None
    padroes = padroes or {}
    titulo = g("titulo")
    if not titulo:
        return None
    url = g("url") or ""
    fid = g("id") or hashlib.sha1(f"{url}|{titulo}|{g('inicio')}".encode()).hexdigest()[:20]
    local = LocalBruto(nome=str(g("local_nome") or ""), endereco=str(g("endereco") or ""), cidade=str(g("cidade") or padroes.get("cidade", "")),
                       estado=str(g("estado") or padroes.get("estado", "")), pais=str(g("pais") or padroes.get("pais", "")), cep=str(g("cep") or ""),
                       lat=_f(g("lat")), lon=_f(g("lon")))
    img = g("imagem")
    img = img[0] if isinstance(img, list) and img else img
    img = img.get("url") if isinstance(img, dict) else img
    org = g("organizador") or padroes.get("organizador")
    return EventoBruto(
        fonte=fonte, fonte_id=str(fid), titulo=str(titulo), descricao=str(g("descricao") or ""), inicio=parse_data(g("inicio"), padroes.get("fuso", "America/Sao_Paulo")),
        fim=parse_data(g("fim"), padroes.get("fuso", "America/Sao_Paulo")), fuso=padroes.get("fuso", ""), local=local if (local.nome or local.endereco or local.lat is not None) else None,
        categorias=_lista(g("categoria")) or _lista(padroes.get("categorias")), artistas=[Pessoa(nome=str(a)) for a in _lista(g("artistas"))],
        organizador=Pessoa(nome=str(org), tipo="organizador") if org else None, imagens=[ImagemBruta(url=str(img), credito=str(padroes.get("credito_imagem", "")))] if img else [],
        preco_min=_f(g("preco_min")), preco_max=_f(g("preco_max")), moeda=str(g("moeda") or padroes.get("moeda", "")),
        gratuito=(True if str(g("gratuito")).lower() in ("1", "true", "sim", "gratis", "grátis") else None) if g("gratuito") is not None else None,
        status_raw=str(g("status") or ""), url=str(url), ingresso_url=str(g("ingresso_url") or ""))


def linhas_csv(texto: str, delimitador: str | None = None):
    amostra = texto[:2000]
    if delimitador is None:
        delimitador = ";" if amostra.count(";") > amostra.count(",") else ","
    yield from csv.DictReader(io.StringIO(texto), delimiter=delimitador)


def linhas_xlsx(conteudo: bytes):
    from openpyxl import load_workbook
    ws = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True).active
    it = ws.iter_rows(values_only=True)
    cab = [str(c).strip() if c is not None else "" for c in next(it, [])]
    for linha in it:
        yield {cab[i]: v for i, v in enumerate(linha) if i < len(cab) and cab[i] and v is not None}
