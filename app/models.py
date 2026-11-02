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
