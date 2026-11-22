"""Sessões de servidor: token aleatório de 256 bits (só o hash SHA-256 fica no banco), expiração absoluta e por inatividade,
revogação, cookie HttpOnly + CSRF derivado por HMAC. Aceita também 'Authorization: Bearer' (apps nativos), sem CSRF."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..seguranca import config
from ..seguranca.ip import cliente_ip, ip_hash
from ..seguranca.modelos import Sessao, Usuario

COOKIE, COOKIE_CSRF = "turiz_sessao", "turiz_csrf"
DURACAO = timedelta(days=30)          # limite absoluto
OCIOSA = timedelta(days=7)            # sem uso
MAX_SESSOES = 10
REAUTH_VALIDA = timedelta(minutes=5)


def agora() -> datetime:
    return datetime.now(timezone.utc)


def utc(d: datetime | None) -> datetime | None:
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_de(token: str) -> str:
    return hmac.new(config.segredo_hmac(), b"csrf:" + token.encode(), hashlib.sha256).hexdigest()[:32]


def criar(db: Session, usuario: Usuario, request: Request, mfa_ok: bool) -> str:
    """Cria a sessão e devolve o token em texto puro (única vez em que existe fora do cliente)."""
    token = secrets.token_urlsafe(32)
    ativas = db.scalars(select(Sessao).where(Sessao.usuario_id == usuario.id, Sessao.revogada_em.is_(None)).order_by(Sessao.criado_em)).all()
    for velha in ativas[: max(0, len(ativas) - MAX_SESSOES + 1)]:       # teto de dispositivos: revoga as mais antigas
        velha.revogada_em = agora()
    db.add(Sessao(token_hash=hash_token(token), usuario_id=usuario.id, expira_em=agora() + DURACAO, dispositivo=(request.headers.get("user-agent", "")[:110]),
                  ip_hash=ip_hash(cliente_ip(request)), mfa_ok=mfa_ok, reauth_em=agora()))
    db.commit()
    return token


def definir_cookies(response: Response, request: Request, token: str):
    seguro = config.https_obrigatorio() or request.url.scheme == "https"
    maxage = int(DURACAO.total_seconds())
    response.set_cookie(COOKIE, token, max_age=maxage, httponly=True, secure=seguro, samesite="lax", path="/")
    response.set_cookie(COOKIE_CSRF, csrf_de(token), max_age=maxage, httponly=False, secure=seguro, samesite="lax", path="/")


def limpar_cookies(response: Response):
    response.delete_cookie(COOKIE, path="/")
    response.delete_cookie(COOKIE_CSRF, path="/")


def _token_da_requisicao(request: Request) -> tuple[str | None, bool]:
    """-> (token, veio_por_cookie)."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip(), False
    return request.cookies.get(COOKIE), True


def _origem_ok(request: Request) -> bool:
    origem = request.headers.get("origin")
    if not origem:
        return True                                  # requisições sem Origin (não-navegador) caem na checagem do token CSRF
    host = request.headers.get("host", "")
    return origem.split("://", 1)[-1] == host or origem in config.origens_cors()


class Autenticado:
    def __init__(self, usuario: Usuario, sessao: Sessao, token: str):
        self.usuario, self.sessao, self.token = usuario, sessao, token


def sessao_atual(request: Request, db: Session = Depends(get_db)) -> Autenticado:
    token, por_cookie = _token_da_requisicao(request)
    nao = HTTPException(401, "Não autenticado")
    if not token:
        raise nao
    s = db.scalar(select(Sessao).where(Sessao.token_hash == hash_token(token)))
    agora_ = agora()
    if s is None or s.revogada_em is not None or utc(s.expira_em) < agora_ or agora_ - utc(s.ultimo_uso_em) > OCIOSA:
        raise nao
    if por_cookie and request.method not in ("GET", "HEAD", "OPTIONS"):
        enviado = request.headers.get("x-csrf-token", "")
        if not _origem_ok(request) or not hmac.compare_digest(enviado.encode(), csrf_de(token).encode()):
            raise HTTPException(403, "Verificação CSRF falhou")
    u = db.get(Usuario, s.usuario_id)
    if u is None:
        raise nao
    if agora_ - utc(s.ultimo_uso_em) > timedelta(seconds=60):
        s.ultimo_uso_em = agora_
        db.commit()
    return Autenticado(u, s, token)


def exigir_reauth(a: Autenticado = Depends(sessao_atual)) -> Autenticado:
    """Operações sensíveis pedem senha recente (últimos 5 minutos)."""
    if a.sessao.reauth_em is None or agora() - utc(a.sessao.reauth_em) > REAUTH_VALIDA:
        raise HTTPException(403, "Confirme sua senha para continuar", headers={"X-Reauth": "necessaria"})
    return a


def exigir_admin(a: Autenticado = Depends(sessao_atual)) -> Autenticado:
    """Administrador SÓ com MFA concluído na sessão."""
    if a.usuario.papel != "admin":
        raise HTTPException(403, "Sem permissão")
    if not a.usuario.mfa_ativo or not a.sessao.mfa_ok:
        raise HTTPException(403, "Verificação em duas etapas obrigatória para administradores")
    return a
