"""Configuração de segurança lida SÓ de variáveis de ambiente (nunca do código). Valores padrão seguros."""
import os


def _int(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, padrao))
    except ValueError:
        return padrao


def producao() -> bool:
    return os.getenv("TURIZ_ENV", "dev").lower() in ("producao", "production", "prod")


def docs_ligados() -> bool:
    """Swagger/OpenAPI só quando pedido explicitamente (TURIZ_DOCS=1) e nunca em produção."""
    return os.getenv("TURIZ_DOCS", "0") == "1" and not producao()


def hosts_permitidos() -> list[str]:
    return [h.strip() for h in os.getenv("TURIZ_ALLOWED_HOSTS", "").split(",") if h.strip()]


def origens_cors() -> list[str]:
    return [o.strip() for o in os.getenv("TURIZ_CORS_ORIGINS", "").split(",") if o.strip()]


def saltos_proxy() -> int:
    """Quantos proxies confiáveis existem na frente da API (CDN/WAF/balanceador). 0 = não confiar em X-Forwarded-For."""
    return max(0, _int("TURIZ_PROXY_HOPS", 0))


def max_corpo_bytes() -> int:
    return _int("TURIZ_MAX_BODY", 1_000_000)          # 1 MB para JSON comum


def max_corpo_ingest_bytes() -> int:
    return _int("TURIZ_MAX_BODY_INGEST", 8_000_000)   # lotes dos bots


def max_itens_ingest() -> int:
    return _int("TURIZ_MAX_INGEST_ITENS", 5000)


def timeout_requisicao_s() -> int:
    return _int("TURIZ_TIMEOUT_S", 30)


def segredo_hmac() -> bytes:
    """Chave para HMAC de IPs/CSRF. Em produção é obrigatória; em dev gera-se uma aleatória por processo."""
    v = os.getenv("TURIZ_HMAC_KEY", "")
    if v:
        return v.encode()
    if producao():
        raise RuntimeError("TURIZ_HMAC_KEY é obrigatória em produção")
    global _EFEMERA
    try:
        return _EFEMERA
    except NameError:
        _EFEMERA = os.urandom(32)
        return _EFEMERA


def https_obrigatorio() -> bool:
    return producao() or os.getenv("TURIZ_FORCE_HTTPS", "0") == "1"
