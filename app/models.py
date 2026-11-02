from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Text, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def agora():
    return datetime.now(timezone.utc)


class Lugar(Base):
    """Restaurante ou bar."""
    __tablename__ = "lugares"
    __table_args__ = (UniqueConstraint("fonte", "fonte_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fonte: Mapped[str] = mapped_column(String(30), index=True)
    fonte_id: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(20), index=True)  # restaurante | bar
    nome: Mapped[str] = mapped_column(String(300), index=True, default="")
    culinaria: Mapped[str] = mapped_column(String(200), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    endereco: Mapped[str] = mapped_column(String(400), default="")
    bairro: Mapped[str] = mapped_column(String(120), index=True, default="")
    cep: Mapped[str] = mapped_column(String(20), default="")
    telefone: Mapped[str] = mapped_column(String(80), default="")
    site: Mapped[str] = mapped_column(String(400), default="")
    horario: Mapped[str] = mapped_column(String(400), default="")
    nota: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)


class Evento(Base):
    __tablename__ = "eventos"
    __table_args__ = (UniqueConstraint("fonte", "fonte_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fonte: Mapped[str] = mapped_column(String(30), index=True)
    fonte_id: Mapped[str] = mapped_column(String(200))
    titulo: Mapped[str] = mapped_column(String(400), index=True, default="")
    descricao: Mapped[str] = mapped_column(Text, default="")
    inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    local_nome: Mapped[str] = mapped_column(String(300), default="")
    endereco: Mapped[str] = mapped_column(String(400), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    url: Mapped[str] = mapped_column(String(500), default="")
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)


class Imagem(Base):
    """Referência a uma imagem de um lugar (guardamos só a URL + licença/autor, não o arquivo)."""
    __tablename__ = "imagens"
    __table_args__ = (UniqueConstraint("lugar_fonte", "lugar_fonte_id", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lugar_fonte: Mapped[str] = mapped_column(String(30), index=True)
    lugar_fonte_id: Mapped[str] = mapped_column(String(200), index=True)
    fonte: Mapped[str] = mapped_column(String(30), index=True)  # commons | osm_image | site
    url: Mapped[str] = mapped_column(String(600))
    thumb_url: Mapped[str] = mapped_column(String(600), default="")
    largura: Mapped[int | None] = mapped_column(nullable=True)
    altura: Mapped[int | None] = mapped_column(nullable=True)
    licenca: Mapped[str] = mapped_column(String(120), default="")
    autor: Mapped[str] = mapped_column(String(300), default="")
    creditos_url: Mapped[str] = mapped_column(String(600), default="")
    # aprovada = licença livre identificada; pendente = precisa de revisão/permissão antes de publicar
    status: Mapped[str] = mapped_column(String(20), index=True, default="pendente")
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)
