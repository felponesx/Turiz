"""Ticketmaster Discovery API v2 (https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/).

Só usa parâmetros e campos DOCUMENTADOS (lidos da documentação oficial em 2026-11-14). Pontos relevantes:
 - autenticação: parâmetro `apikey` (chave em TICKETMASTER_API_KEY; nunca no código, no front, na resposta da API ou nos logs);
 - limites: 5000 chamadas/dia e 5 requisições/segundo; paginação profunda só até size*page < 1000;
 - `latlong` é obsoleto: use `geoPoint` (geohash); `source` aceita ticketmaster, universe, frontgate, tmr (padrão: todas);
 - o Brasil (BR) consta na lista de códigos de país aceitos, mas NÃO consta nos textos de cobertura nem nos mercados (marketId/dmaId):
   quantos eventos brasileiros existem só se sabe com uma consulta real (veja `validar_credencial`).
Não documentado, portanto não presumido: ageRestrictions, formato de startDateTime (usamos ISO 8601 UTC) e o conteúdo de `accessibility`.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Iterator
from urllib.parse import urlparse
from ..bruto import EventoBruto, ImagemBruta, LocalBruto, Pessoa
from ..geo import geohash
from .base import Conector, Contexto, CredencialInvalida, ErroFonte, Requisitor, SemCredencial, redigir, registrar

RAIZ = "https://app.ticketmaster.com/discovery/v2/"
ENDPOINT = RAIZ + "events.json"
LIMITE_PROFUNDO = 1000                     # "size * page < 1000"
VARIAVEL_PADRAO = "TICKETMASTER_API_KEY"
# parâmetros de busca de eventos documentados (seção Event Search); qualquer outro é recusado
PARAMS_DOCUMENTADOS = {
    "id", "keyword", "attractionId", "venueId", "postalCode", "latlong", "radius", "unit", "source", "locale", "marketId",
    "startDateTime", "endDateTime", "includeTBA", "includeTBD", "includeTest", "size", "page", "sort", "onsaleStartDateTime",
    "onsaleEndDateTime", "city", "countryCode", "stateCode", "classificationName", "classificationId", "dmaId", "localStartDateTime",
    "localStartEndDateTime", "startEndDateTime", "publicVisibilityStartDateTime", "preSaleDateTime", "onsaleOnStartDate",
    "onsaleOnAfterStartDate", "collectionId", "segmentId", "segmentName", "includeFamily", "promoterId", "genreId", "subGenreId",
    "typeId", "subTypeId", "geoPoint", "preferredCountry", "includeSpellcheck", "domain",
}
FONTES_TM = {"ticketmaster", "universe", "frontgate", "tmr"}
SP = (-23.5505, -46.6333)                 # Praça da Sé

# consultas padrão: Brasil inteiro, depois a região de São Paulo (cidade e raio), sem restringir `source`
CONSULTAS_PADRAO = [
    {"nome": "brasil", "countryCode": "BR"},
    {"nome": "sao-paulo-cidade", "countryCode": "BR", "city": "São Paulo"},
    {"nome": "sao-paulo-regiao", "geoPoint": geohash(*SP, 7), "radius": 80, "unit": "km"},
]


def formatar_data(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validar_params(p: dict) -> dict:
    desconhecidos = set(p) - PARAMS_DOCUMENTADOS - {"nome"}
    if desconhecidos:
        raise ValueError(f"parâmetros não documentados pela Ticketmaster: {sorted(desconhecidos)}")
    if "source" in p:
        for s in str(p["source"]).replace(" ", "").split(","):
            if s not in FONTES_TM:
                raise ValueError(f"source inválido: {s} (use {sorted(FONTES_TM)})")
    if "unit" in p and p["unit"] not in ("miles", "km"):
        raise ValueError("unit deve ser 'miles' ou 'km'")
    return {k: v for k, v in p.items() if k != "nome"}


def chave_de(config: dict) -> str:
    return (os.getenv(config.get("chave_env") or VARIAVEL_PADRAO) or "").strip()


def plataforma_da_url(url: str) -> str:
    """Origem dentro da API, inferida do domínio do link (heurística: a doc não traz o campo). Padrão: ticketmaster."""
    h = (urlparse(url or "").netloc or "").lower()
    if "universe.com" in h:
        return "universe"
    if "frontgatetickets" in h:
        return "frontgate"
    return "ticketmaster"


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _data_inicio(dates: dict):
    """-> (inicio UTC | None, data_incerta, hora_incerta, fuso)."""
    ini = (dates or {}).get("start") or {}
    fuso = (dates or {}).get("timezone", "")
    incerta = bool(ini.get("dateTBD") or ini.get("dateTBA"))
    if ini.get("dateTime") and not incerta:
        try:
            return datetime.fromisoformat(ini["dateTime"].replace("Z", "+00:00")), False, bool(ini.get("timeTBA") or ini.get("noSpecificTime")), fuso
        except ValueError:
            pass
    if ini.get("localDate") and not incerta:
        try:
            from zoneinfo import ZoneInfo
            dia = datetime.fromisoformat(ini["localDate"] + "T" + (ini.get("localTime") or "00:00:00"))
            tz = ZoneInfo(fuso) if fuso else timezone.utc
            return dia.replace(tzinfo=tz), False, not ini.get("localTime"), fuso
        except Exception:
            pass
    return None, incerta, True, fuso


def normalizar_evento(ev: dict, fonte: str = "ticketmaster", source_filtro: str = "") -> EventoBruto | None:
    """Evento da API -> EventoBruto. Só copia o que a API informou."""
    if not ev.get("id") or not ev.get("name"):
        return None
    emb = ev.get("_embedded") or {}
    v = (emb.get("venues") or [{}])[0] or {}
    cidade = ((v.get("city") or {}).get("name")) or ""
    loc = (v.get("location") or {})
    addr = v.get("address") or {}
    local = LocalBruto(nome=v.get("name", ""), endereco=", ".join(x for x in (addr.get("line1"), addr.get("line2")) if x), cidade=cidade,
                       estado=(v.get("state") or {}).get("stateCode") or (v.get("state") or {}).get("name", ""),
                       pais=(v.get("country") or {}).get("countryCode") or (v.get("country") or {}).get("name", ""),
                       cep=v.get("postalCode", ""), lat=_f(loc.get("latitude")), lon=_f(loc.get("longitude")), fonte_id=v.get("id", "")) if v else None
    inicio, incerta, hora_incerta, fuso = _data_inicio(ev.get("dates") or {})
    fim = None
    fim_d = ((ev.get("dates") or {}).get("end") or {}).get("dateTime")
    if fim_d:
        try:
            fim = datetime.fromisoformat(fim_d.replace("Z", "+00:00"))
        except ValueError:
            pass
    termos, vistos = [], set()
    for c in ev.get("classifications") or []:
        for chave in ("segment", "genre", "subGenre", "type", "subType"):
            nome = (c.get(chave) or {}).get("name")
            if nome and nome not in vistos and nome.lower() != "undefined":
                vistos.add(nome)
                termos.append(nome)
    artistas = [Pessoa(nome=a.get("name", ""), fonte_id=a.get("id", ""), url=a.get("url", ""),
                       imagem_url=next((i.get("url", "") for i in (a.get("images") or []) if not i.get("fallback")), ""))
                for a in emb.get("attractions") or [] if a.get("name")]
    for a in emb.get("attractions") or []:       # gênero do artista também ajuda a classificar
        for c in a.get("classifications") or []:
            for chave in ("segment", "genre", "subGenre"):
                nome = (c.get(chave) or {}).get("name")
                if nome and nome not in vistos and nome.lower() != "undefined":
                    vistos.add(nome)
                    termos.append(nome)
    organizador = None
    promoter = ev.get("promoter") or (ev.get("promoters") or [None])[0]
    if promoter and promoter.get("name"):         # a API às vezes só traz o id: sem nome, não inventamos
        organizador = Pessoa(nome=promoter["name"], fonte_id=str(promoter.get("id", "")), tipo="promotor")
    imagens = [ImagemBruta(url=i.get("url", ""), largura=i.get("width"), altura=i.get("height"), proporcao=i.get("ratio", ""), fallback=bool(i.get("fallback")))
               for i in ev.get("images") or [] if i.get("url")]
    precos = [p for p in ev.get("priceRanges") or [] if isinstance(p, dict)]
    pmin = min((x for x in (_f(p.get("min")) for p in precos) if x is not None), default=None)
    pmax = max((x for x in (_f(p.get("max")) for p in precos) if x is not None), default=None)
    info = " ".join(x for x in (ev.get("info"), ev.get("pleaseNote")) if x)
    acess = ev.get("accessibility")
    acess = acess if isinstance(acess, str) else (json.dumps(acess, ensure_ascii=False)[:1000] if acess else "")
    url = ev.get("url", "")
    extra = {"promoter_id": str((ev.get("promoter") or {}).get("id", "")) or None, "status_venda": ((ev.get("dates") or {}).get("status") or {}).get("code"),
             "hora_incerta": hora_incerta or None, "venda_publica_inicio": (((ev.get("sales") or {}).get("public")) or {}).get("startDateTime"),
             "venda_publica_fim": (((ev.get("sales") or {}).get("public")) or {}).get("endDateTime"),
             "idade_legal_exigida": (ev.get("ageRestrictions") or {}).get("legalAgeEnforced"),
             "plataforma_inferida": None if source_filtro else True}
    return EventoBruto(
        fonte=fonte, fonte_id=str(ev["id"]), titulo=ev["name"], plataforma=source_filtro or plataforma_da_url(url), descricao=info, inicio=inicio, fim=fim, fuso=fuso,
        data_incerta=incerta, local=local, categorias=termos, artistas=artistas, organizador=organizador, imagens=imagens, acessibilidade=acess,
        preco_min=pmin, preco_max=pmax, moeda=(precos[0].get("currency", "") if precos else ""),
        gratuito=True if (pmax is not None and pmax == 0) else None, status_raw=((ev.get("dates") or {}).get("status") or {}).get("code", ""),
        url=url, ingresso_url=url, extra={k: x for k, x in extra.items() if x is not None})


@registrar
class Ticketmaster(Conector):
    tipo = "ticketmaster"
    descricao = "Ticketmaster Discovery API v2 (Ticketmaster, Universe, FrontGate Tickets e Ticketmaster Resale)"
    requer_credencial = True

    def credencial_ok(self, config: dict) -> bool:
        return bool(chave_de(config))

    def coletar(self, ctx: Contexto) -> Iterator[EventoBruto]:
        chave = chave_de(ctx.config)
        if not chave:
            raise SemCredencial(f"defina a variável de ambiente {ctx.config.get('chave_env') or VARIAVEL_PADRAO}")
        req = ctx.requisitor
        req.segredos = tuple(req.segredos) + (chave,)
        size = min(int(ctx.config.get("tamanho_pagina", 200)), 200)
        max_req = int(ctx.config.get("max_requisicoes", 300))
        piso_quota = int(ctx.config.get("quota_minima", 100))
        consultas = ctx.config.get("consultas") or CONSULTAS_PADRAO
        a_partir_de = ctx.agora
        entregues = set()
        for q in consultas:
            params = validar_params(dict(q))
            params.setdefault("locale", "*")
            params.setdefault("sort", "date,asc")
            params.setdefault("startDateTime", formatar_data(a_partir_de))
            if "endDateTime" not in params:
                params["endDateTime"] = formatar_data(a_partir_de + timedelta(days=int(ctx.config.get("dias_a_frente", 365))))
            params["size"] = size
            for ev in self._janela(ctx, req, chave, params, max_req, piso_quota):
                if ev["id"] in entregues:
                    continue
                entregues.add(ev["id"])
                b = normalizar_evento(ev, ctx.slug, params.get("source", ""))
                if b:
                    yield b
                    if ctx.limite and len(entregues) >= ctx.limite:
                        return

    def _pagina(self, req: Requisitor, chave: str, params: dict, pagina: int):
        try:
            return req.get_json(ENDPOINT, params={**params, "page": pagina, "apikey": chave})
        except CredencialInvalida:
            raise
        except ErroFonte as exc:
            raise type(exc)(redigir(str(exc), (chave,)))

    def _janela(self, ctx, req, chave, params, max_req, piso_quota):
        """Coleta todas as páginas de uma janela de datas; se houver mais de 1000 itens, divide a janela ao meio."""
        j = self._pagina(req, chave, params, 0)
        ctx.stats.paginas += 1
        info = j.get("page") or {}
        total, paginas = int(info.get("totalElements", 0)), int(info.get("totalPages", 0))
        size = int(params["size"])
        if total > LIMITE_PROFUNDO and self._dividir(params):
            for sub in self._dividir(params):
                if req.stats.requisicoes >= max_req:
                    ctx.stats.parcial, ctx.stats.mensagem = True, "limite de requisições da execução atingido"
                    return
                yield from self._janela(ctx, req, chave, sub, max_req, piso_quota)
            return
        yield from (j.get("_embedded") or {}).get("events", [])
        for pagina in range(1, paginas):
            if pagina * size >= LIMITE_PROFUNDO:           # regra documentada: size * page < 1000
                ctx.stats.parcial, ctx.stats.mensagem = True, f"janela com {total} eventos: paginação limitada a {LIMITE_PROFUNDO} itens pela API"
                return
            if req.stats.requisicoes >= max_req or (req.stats.quota_restante is not None and req.stats.quota_restante < piso_quota):
                ctx.stats.parcial, ctx.stats.mensagem = True, "quota/limite de requisições protegido: coleta interrompida"
                return
            jp = self._pagina(req, chave, params, pagina)
            ctx.stats.paginas += 1
            yield from (jp.get("_embedded") or {}).get("events", [])

    @staticmethod
    def _dividir(params: dict):
        """Divide a janela [startDateTime, endDateTime] em duas; None se já for pequena demais (≤ 1 dia)."""
        try:
            ini = datetime.strptime(params["startDateTime"], "%Y-%m-%dT%H:%M:%SZ")
            fim = datetime.strptime(params["endDateTime"], "%Y-%m-%dT%H:%M:%SZ")
        except (KeyError, ValueError):
            return None
        if fim - ini <= timedelta(days=1):
            return None
        meio = ini + (fim - ini) / 2
        meio = meio.replace(microsecond=0)
        return [{**params, "startDateTime": params["startDateTime"], "endDateTime": meio.strftime("%Y-%m-%dT%H:%M:%SZ")},
                {**params, "startDateTime": (meio + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"), "endDateTime": params["endDateTime"]}]


def validar_credencial(config: dict | None = None, client=None) -> dict:
    """Consulta REAL mínima (size=1) para saber se a chave funciona e se há eventos no Brasil/São Paulo.
    Só retorna ok=True com resposta HTTP 200 da API. Não imprime a chave."""
    config = config or {}
    chave = chave_de(config)
    if not chave:
        return {"ok": False, "status": "aguardando_credencial", "mensagem": f"{config.get('chave_env') or VARIAVEL_PADRAO} não definida"}
    req = Requisitor(client=client, segredos=(chave,), tentativas=2)
    saida = {"ok": False, "status": "erro", "mensagem": "", "eventos_brasil": None, "eventos_sao_paulo": None}
    try:
        for rotulo, extra in (("eventos_brasil", {"countryCode": "BR"}), ("eventos_sao_paulo", {"countryCode": "BR", "city": "São Paulo"})):
            j = req.get_json(ENDPOINT, params={"apikey": chave, "size": 1, "locale": "*", **extra})
            saida[rotulo] = int((j.get("page") or {}).get("totalElements", 0))
        saida.update(ok=True, status="sucesso", quota_restante=req.stats.quota_restante)
    except CredencialInvalida as exc:
        saida.update(status="chave_invalida", mensagem=redigir(str(exc), (chave,)))
    except ErroFonte as exc:
        saida.update(status=exc.status, mensagem=redigir(str(exc), (chave,)))
    return saida
