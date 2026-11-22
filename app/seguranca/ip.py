"""IP do cliente e pseudonimização (LGPD: não guardamos IP puro)."""
import hashlib
import hmac
from fastapi import Request
from . import config


def cliente_ip(request: Request) -> str:
    """IP de quem fez a requisição. X-Forwarded-For só é considerado quando há proxies confiáveis configurados
    (TURIZ_PROXY_HOPS): pegamos o N-ésimo da direita, que foi escrito pelo NOSSO proxy, e não o valor que o cliente mandou."""
    peer = request.client.host if request.client else "?"
    n = config.saltos_proxy()
    if n:
        xff = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(xff) >= n:
            return xff[-n]
    return peer


def ip_hash(ip: str) -> str:
    return hmac.new(config.segredo_hmac(), ip.encode(), hashlib.sha256).hexdigest()[:20]


def cliente_ip_scope(scope) -> str:
    """Mesma regra de `cliente_ip`, a partir do scope ASGI (usado no middleware)."""
    peer = (scope.get("client") or ("?", 0))[0]
    n = config.saltos_proxy()
    if n:
        h = dict(scope.get("headers") or [])
        xff = [p.strip() for p in h.get(b"x-forwarded-for", b"").decode("latin-1").split(",") if p.strip()]
        if len(xff) >= n:
            return xff[-n]
    return peer
