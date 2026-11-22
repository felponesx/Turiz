"""Camada de proteção em torno de TODA a API (ASGI puro): cabeçalhos de segurança, limite de corpo, limite de requisições por IP e
classe de rota, controle de concorrência em rotas caras, timeout, tratamento seguro de erros e identificador de requisição."""
import asyncio
import json
import logging
import secrets
from . import config, limites
from .ip import cliente_ip_scope

log = logging.getLogger("turiz.seguranca")

CSP_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
# página estática embutida (mapa Leaflet + OpenStreetMap): scripts só do próprio site e do cdnjs
CSP_PAGINA = ("default-src 'self'; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
              "img-src 'self' data: https:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")


def _json(status: int, corpo: dict, extra: list | None = None):
    dados = json.dumps(corpo, ensure_ascii=False).encode()
    cab = [(b"content-type", b"application/json; charset=utf-8"), (b"content-length", str(len(dados)).encode())] + (extra or [])
    return status, cab, dados


class SegurancaMiddleware:
    def __init__(self, app):
        self.app = app
        self._caros = asyncio.Semaphore(int(__import__("os").getenv("TURIZ_CONCORRENCIA_CARA", "6")))

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        rid = secrets.token_hex(8)
        scope.setdefault("state", {})["request_id"] = rid
        metodo, caminho = scope["method"], scope["path"]
        qs = scope.get("query_string", b"").decode("latin-1")
        tem_busca = any(k in qs for k in ("q=", "aberto_agora=", "bairro=", "culinaria=")) or "busca" in caminho
        ip = cliente_ip_scope(scope)
        eh_pagina = not caminho.startswith(("/lugares", "/eventos", "/avaliacoes", "/ingest", "/imagens", "/admin", "/conta", "/health", "/docs", "/openapi"))

        async def responder(status, cab, corpo=b""):
            await send({"type": "http.response.start", "status": status, "headers": self._cab_seg(cab, eh_pagina, rid, caminho)})
            await send({"type": "http.response.body", "body": corpo})

        # 1) limite de requisições (por IP e classe de rota)
        lim = limites.classe_da_rota(metodo, caminho, tem_busca)
        ok, espera = lim.verificar(ip)
        if not ok:
            return await responder(*_json(429, {"detail": "Muitas requisições; tente novamente em instantes", "request_id": rid},
                                          [(b"retry-after", str(max(1, espera)).encode())]))
        # 2) limite de corpo (Content-Length e fluxo)
        limite = config.max_corpo_ingest_bytes() if caminho.startswith("/ingest") else config.max_corpo_bytes()
        cl = dict(scope["headers"]).get(b"content-length")
        if cl and cl.isdigit() and int(cl) > limite:
            return await responder(*_json(413, {"detail": "Corpo da requisição grande demais", "request_id": rid}))
        recebido = 0

        async def receive_limitado():
            nonlocal recebido
            msg = await receive()
            if msg["type"] == "http.request":
                recebido += len(msg.get("body", b""))
                if recebido > limite:
                    raise _CorpoGrande()
            return msg

        iniciou = False

        async def send_marcado(msg):
            nonlocal iniciou
            if msg["type"] == "http.response.start":
                iniciou = True
                msg = {**msg, "headers": self._cab_seg(list(msg.get("headers", [])), eh_pagina, rid, caminho)}
            await send(msg)

        # 3) concorrência em rotas caras + 4) timeout + 5) erros sem vazar detalhes
        cara = lim is limites.CARA
        try:
            if cara:
                try:
                    await asyncio.wait_for(self._caros.acquire(), timeout=0.05)
                except asyncio.TimeoutError:
                    return await responder(*_json(503, {"detail": "Serviço ocupado; tente novamente em instantes", "request_id": rid}, [(b"retry-after", b"5")]))
            try:
                await asyncio.wait_for(self.app(scope, receive_limitado, send_marcado), timeout=config.timeout_requisicao_s())
            finally:
                if cara:
                    self._caros.release()
        except _CorpoGrande:
            if not iniciou:
                await responder(*_json(413, {"detail": "Corpo da requisição grande demais", "request_id": rid}))
        except asyncio.TimeoutError:
            if not iniciou:
                await responder(*_json(504, {"detail": "Tempo esgotado", "request_id": rid}))
        except Exception as exc:                      # nunca devolve stack trace nem mensagem interna
            log.error("erro interno request_id=%s tipo=%s rota=%s", rid, type(exc).__name__, caminho)
            if not iniciou:
                await responder(*_json(500, {"detail": "Erro interno", "request_id": rid}))

    @staticmethod
    def _cab_seg(cab: list, eh_pagina: bool, rid: str, caminho: str) -> list:
        nomes = {k.lower() for k, _ in cab}
        extra = {
            b"x-content-type-options": b"nosniff", b"referrer-policy": b"strict-origin-when-cross-origin",
            b"permissions-policy": b"camera=(), microphone=(), payment=(), geolocation=(self)", b"x-frame-options": b"DENY",
            b"cross-origin-opener-policy": b"same-origin", b"cross-origin-resource-policy": b"same-site",
            b"content-security-policy": (config.csp_pagina(CSP_PAGINA) if eh_pagina else CSP_API).encode(), b"x-request-id": rid.encode(),
        }
        if config.https_obrigatorio():
            extra[b"strict-transport-security"] = b"max-age=31536000; includeSubDomains"
        if caminho.startswith(("/admin", "/conta")):
            extra[b"cache-control"] = b"no-store"                 # nada de dados administrativos/pessoais em cache
        return [(k, v) for k, v in cab if k.lower() not in extra] + list(extra.items())

class _CorpoGrande(Exception):
    pass
