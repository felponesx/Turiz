"""Conectores de feeds e planilhas de organizadores/parceiros: JSON, XML, RSS/Atom, CSV/XLSX, JSON-LD de sites.

Configuração (fontes_eventos.yml): url (ou caminho local `arquivo`), `itens` (onde está a lista), `mapa` (campo Turiz -> caminho) e `padroes`.
Respeita robots.txt em URLs de site (feeds oficiais e arquivos do parceiro dispensam, pois foram publicados para consumo automático)."""
import time
from pathlib import Path
from typing import Iterator
import httpx
from defusedxml import ElementTree as ET
from ..bruto import EventoBruto
from .base import Conector, Contexto, ErroFonte, FonteBloqueada, registrar
from .comum import caminho, de_mapa, linhas_csv, linhas_xlsx

MAPA_RSS = {"titulo": "title", "url": "link", "id": "guid", "descricao": "description", "inicio": "pubDate", "categoria": "category", "imagem": "enclosure"}


def _baixar(ctx: Contexto, url: str) -> httpx.Response:
    try:
        r = ctx.requisitor.client.get(url)
    except httpx.HTTPError as exc:
        raise ErroFonte(f"{type(exc).__name__} ao baixar a fonte")
    if r.status_code in (401, 403):
        raise FonteBloqueada(f"acesso negado (HTTP {r.status_code})")
    if r.status_code >= 400:
        raise ErroFonte(f"HTTP {r.status_code}")
    ctx.stats.requisicoes += 1
    return r


def _conteudo(ctx: Contexto) -> tuple[bytes, str]:
    c = ctx.config
    if c.get("arquivo"):
        return Path(c["arquivo"]).read_bytes(), c["arquivo"]
    if not c.get("url"):
        raise ErroFonte("configure `url` ou `arquivo`")
    r = _baixar(ctx, c["url"])
    return r.content, c["url"]


def _emitir(ctx, itens, fonte, mapa, padroes) -> Iterator[EventoBruto]:
    n = 0
    for it in itens:
        b = de_mapa(it, mapa, fonte, padroes)
        if b:
            yield b
            n += 1
            if ctx.limite and n >= ctx.limite:
                return


@registrar
class FeedJson(Conector):
    tipo = "feed_json"
    descricao = "API/feed JSON de organizador ou parceiro"

    def coletar(self, ctx):
        import json
        dados, _ = _conteudo(ctx)
        try:
            j = json.loads(dados)
        except ValueError:
            raise ErroFonte("JSON inválido")
        itens = caminho(j, ctx.config.get("itens", "")) if ctx.config.get("itens") else j
        if not isinstance(itens, list):
            raise ErroFonte("`itens` não aponta para uma lista")
        yield from _emitir(ctx, itens, ctx.slug, ctx.config.get("mapa") or {}, ctx.config.get("padroes"))


def _xml_para_dict(el) -> dict:
    d = {}
    for ch in el:
        tag = ch.tag.split("}")[-1]
        v = _xml_para_dict(ch) if len(ch) else (ch.text or "").strip()
        if ch.attrib and not len(ch):
            v = ch.attrib.get("url") or ch.attrib.get("href") or v
        d[tag] = v if tag not in d else ([d[tag]] if not isinstance(d[tag], list) else d[tag]) + [v]
    return d


@registrar
class FeedXml(Conector):
    tipo = "feed_xml"
    descricao = "Feed XML de organizador ou parceiro (itens configuráveis)"

    def coletar(self, ctx):
        dados, _ = _conteudo(ctx)
        try:
            raiz = ET.fromstring(dados)              # defusedxml: sem entidades externas / bombas de expansão
        except ET.ParseError:
            raise ErroFonte("XML inválido")
        tag = ctx.config.get("item", "event")
        itens = [_xml_para_dict(e) for e in raiz.iter() if e.tag.split("}")[-1] == tag]
        yield from _emitir(ctx, itens, ctx.slug, ctx.config.get("mapa") or {}, ctx.config.get("padroes"))


@registrar
class Rss(FeedXml):
    tipo = "rss"
    descricao = "RSS 2.0 / Atom"

    def coletar(self, ctx):
        dados, _ = _conteudo(ctx)
        try:
            raiz = ET.fromstring(dados)
        except ET.ParseError:
            raise ErroFonte("XML inválido")
        itens = [_xml_para_dict(e) for e in raiz.iter() if e.tag.split("}")[-1] in ("item", "entry")]
        for it in itens:                              # Atom: <link href> já vira string pela função acima
            if isinstance(it.get("link"), list):
                it["link"] = it["link"][0]
        yield from _emitir(ctx, itens, ctx.slug, {**MAPA_RSS, **(ctx.config.get("mapa") or {})}, ctx.config.get("padroes"))


@registrar
class Planilha(Conector):
    tipo = "planilha"
    descricao = "Planilha CSV/XLSX enviada por organizador/parceiro (arquivo ou URL)"

    def coletar(self, ctx):
        dados, nome = _conteudo(ctx)
        if nome.lower().endswith((".xlsx", ".xlsm")):
            linhas = linhas_xlsx(dados)
        else:
            linhas = linhas_csv(dados.decode("utf-8-sig", errors="replace"), ctx.config.get("delimitador"))
        mapa = ctx.config.get("mapa") or {k: k for k in ("titulo", "id", "inicio", "fim", "url", "descricao", "imagem", "local_nome", "endereco", "cidade", "estado", "pais",
                                                         "lat", "lon", "preco_min", "preco_max", "categoria", "status", "artistas", "organizador", "ingresso_url", "gratuito")}
        yield from _emitir(ctx, linhas, ctx.slug, mapa, ctx.config.get("padroes"))


def bruto_de_evento_site(e: dict, fonte: str) -> EventoBruto:
    """Dict produzido por `app.sources.sites.extrair` -> EventoBruto (reaproveita o extrator JSON-LD já testado)."""
    from ..bruto import ImagemBruta, LocalBruto
    return EventoBruto(
        fonte=fonte, fonte_id=e["fonte_id"], titulo=e["titulo"], descricao=e.get("descricao", ""), inicio=e.get("inicio"), fim=e.get("fim"),
        local=LocalBruto(nome=e.get("local_nome", ""), endereco=e.get("endereco", ""), lat=e.get("lat"), lon=e.get("lon"), cidade=e.get("_cidade", "")) if (e.get("local_nome") or e.get("endereco")) else None,
        categorias=[e["categoria"]] if e.get("categoria") and e["categoria"] != "evento" else [], imagens=[ImagemBruta(url=e["imagem_url"])] if e.get("imagem_url") else [],
        preco_min=e.get("preco_min"), gratuito=e.get("gratuito") if e.get("preco_min") is not None else None, url=e.get("url", ""), ingresso_url=e.get("ingresso_url", ""))


@registrar
class JsonLd(Conector):
    tipo = "jsonld"
    descricao = "Site de organizador/plataforma com JSON-LD schema.org (respeita robots.txt)"

    def coletar(self, ctx):
        from ...sources import sites
        c = ctx.config
        cli = ctx.requisitor.client
        url, cidade, pausa = c["url"], c.get("cidade", ""), float(c.get("pausa", 2))
        if not sites.permitido(url, cli):
            raise FonteBloqueada("robots.txt não permite a coleta")
        urls = [url]
        try:
            r = sites.obter(cli, url)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise ErroFonte(f"{type(exc).__name__} na página inicial")
        _, evs = sites.extrair(r.text, url, "evento")
        if c.get("listagem"):
            urls = sites.links_listagem(r.text, str(r.url), c["padrao_link"], int(c.get("limite", 30)))
        else:
            urls = []
        n = 0
        for e in evs:
            if sites.da_cidade(e, cidade):
                e["_cidade"] = cidade
                yield bruto_de_evento_site(e, ctx.slug)
        for u in urls:
            if ctx.limite and n >= ctx.limite:
                return
            if not sites.permitido(u, cli):
                ctx.stats.avisos.append("página ignorada pelo robots.txt")
                continue
            try:
                rd = sites.obter(cli, u)
                rd.raise_for_status()
            except httpx.HTTPError:
                ctx.stats.erros += 1
                continue
            ctx.stats.paginas += 1
            _, evs = sites.extrair(rd.text, u, "evento")
            for e in evs:
                if sites.da_cidade(e, cidade):
                    e["_cidade"] = cidade
                    n += 1
                    yield bruto_de_evento_site(e, ctx.slug)
            time.sleep(pausa)
