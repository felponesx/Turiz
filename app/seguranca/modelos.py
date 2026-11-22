"""Tabelas de segurança e de contas de usuário (migração 0003).

Nada aqui guarda segredo em texto puro: senhas são hash Argon2id, tokens de sessão/recuperação são guardados só como SHA-256,
o segredo TOTP é cifrado (Fernet), IPs são guardados só como HMAC truncado (não reversível). Veja docs/seguranca/dados-pessoais.md.
"""
from datetime import datetime, timezone
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base


def agora():
    return datetime.now(timezone.utc)


class Auditoria(Base):
    """Trilha de auditoria de operações administrativas e eventos de segurança. Sem segredos e sem IP puro."""
    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    quando: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)
    ator: Mapped[str] = mapped_column(String(60), default="", index=True)       # nome da chave (nunca o valor) ou "usuario:<id>"
    escopo: Mapped[str] = mapped_column(String(30), default="")
    metodo: Mapped[str] = mapped_column(String(8), default="")
    rota: Mapped[str] = mapped_column(String(200), default="")
    resultado: Mapped[str] = mapped_column(String(16), default="", index=True)  # autorizado | negado | ok | falha | alerta
    ip_hash: Mapped[str] = mapped_column(String(24), default="")
    request_id: Mapped[str] = mapped_column(String(32), default="")
    detalhe: Mapped[str] = mapped_column(String(300), default="")


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_norm: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    email_verificado: Mapped[bool] = mapped_column(Boolean, default=False)
    email_pendente: Mapped[str] = mapped_column(String(254), default="")
    senha_hash: Mapped[str] = mapped_column(String(255))
    nome: Mapped[str] = mapped_column(String(80), default="")
    papel: Mapped[str] = mapped_column(String(12), default="usuario")            # usuario | admin
    mfa_ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_segredo: Mapped[str] = mapped_column(String(255), default="")            # cifrado (Fernet)
    mfa_recuperacao: Mapped[list] = mapped_column(JSON, default=list)            # hashes SHA-256 de códigos de uso único
    mfa_ultimo_passo: Mapped[int] = mapped_column(Integer, default=0)            # último passo TOTP aceito (impede reutilização do código)
    falhas_login: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ultimo_login_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)


class Sessao(Base):
    __tablename__ = "sessoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    ultimo_uso_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispositivo: Mapped[str] = mapped_column(String(120), default="")
    ip_hash: Mapped[str] = mapped_column(String(24), default="")
    mfa_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    reauth_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TokenConta(Base):
    """Tokens de uso único: recuperar senha, verificar e-mail, trocar e-mail. Guardamos só o hash."""
    __tablename__ = "tokens_conta"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    alvo: Mapped[str] = mapped_column(String(254), default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FavoritoUsuario(Base):
    """Favoritos de cada usuário. A API nunca recebe o id do dono: ele vem da sessão (sem IDOR por construção)."""
    __tablename__ = "favoritos_usuario"
    __table_args__ = (UniqueConstraint("usuario_id", "tipo", "ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(12))        # lugar | evento | prato
    ref: Mapped[str] = mapped_column(String(100))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
