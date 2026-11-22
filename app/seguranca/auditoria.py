"""Trilha de auditoria: quem (nome da chave ou usuário), o quê (método + rota sem query), quando e de onde (IP pseudonimizado).
NUNCA grava valores de chaves, senhas, tokens, corpo da requisição nem IP puro."""
import logging
import re
import secrets
from fastapi import Request
from sqlalchemy.orm import Session
from .ip import cliente_ip, ip_hash
from .modelos import Auditoria

log = logging.getLogger("turiz.seguranca")
_SEGREDO = re.compile(r"(?i)(api[_-]?key|token|senha|password|secret|authorization)=[^&\s]+")


def limpar(texto: str, n: int = 300) -> str:
    return _SEGREDO.sub(r"\1=***", str(texto))[:n]


def request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if not rid:
        rid = secrets.token_hex(8)
        request.state.request_id = rid
    return rid


def registrar(db: Session, request: Request | None, ator: str, escopo: str = "", resultado: str = "ok", detalhe: str = "", rota: str | None = None) -> None:
    """Escreve na trilha sem nunca derrubar a requisição por falha de auditoria."""
    try:
        db.add(Auditoria(ator=ator[:60], escopo=escopo[:30], metodo=(request.method if request else "")[:8],
                         rota=limpar(rota if rota is not None else (request.url.path if request else ""), 200),
                         resultado=resultado, ip_hash=ip_hash(cliente_ip(request)) if request else "",
                         request_id=request_id(request) if request else "", detalhe=limpar(detalhe)))
        db.commit()
    except Exception as exc:                      # auditoria falhar não pode abrir brecha nem derrubar o serviço, mas fica no log
        db.rollback()
        log.error("falha ao gravar auditoria: %s", type(exc).__name__)
