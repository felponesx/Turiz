from datetime import datetime, timezone
from sqlalchemy import Boolean, String, Float, DateTime, Text, UniqueConstraint, JSON
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
    # vínculo com o restaurante/bar onde acontece (preenchido por app/sources/vincular.py)
    lugar_fonte: Mapped[str] = mapped_column(String(30), default="", index=True)
    lugar_fonte_id: Mapped[str] = mapped_column(String(200), default="", index=True)
    categoria: Mapped[str] = mapped_column(String(60), default="", index=True)  # musica | gastronomia | teatro | comedia | festa | ...
    imagem_url: Mapped[str] = mapped_column(String(600), default="")
    preco_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    gratuito: Mapped[bool] = mapped_column(Boolean, default=False)
    ingresso_url: Mapped[str] = mapped_column(String(600), default="")
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


class RedeSocial(Base):
    """Perfil de rede social (Instagram) associado a um lugar, com a origem e a confiança do vínculo."""
    __tablename__ = "redes_sociais"
    __table_args__ = (UniqueConstraint("lugar_fonte", "lugar_fonte_id", "rede", "usuario"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lugar_fonte: Mapped[str] = mapped_column(String(30), index=True)
    lugar_fonte_id: Mapped[str] = mapped_column(String(200), index=True)
    rede: Mapped[str] = mapped_column(String(20), default="instagram")
    usuario: Mapped[str] = mapped_column(String(60))
    url: Mapped[str] = mapped_column(String(200), default="")
    origem: Mapped[str] = mapped_column(String(30))  # osm_tag | site | api_oficial | manual
    confianca: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(20), index=True, default="provavel")  # confirmado | provavel | rejeitado
    nome_perfil: Mapped[str] = mapped_column(String(200), default="")
    seguidores: Mapped[int | None] = mapped_column(nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)


class Cardapio(Base):
    """Cardápio de um lugar: link para o cardápio oficial (e itens, quando o site publica em JSON-LD).
    Só a referência pública do próprio estabelecimento; não guardamos PDFs nem imagens."""
    __tablename__ = "cardapios"
    __table_args__ = (UniqueConstraint("lugar_fonte", "lugar_fonte_id", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lugar_fonte: Mapped[str] = mapped_column(String(30), index=True)
    lugar_fonte_id: Mapped[str] = mapped_column(String(200), index=True)
    url: Mapped[str] = mapped_column(String(600))
    plataforma: Mapped[str] = mapped_column(String(30), default="proprio")  # proprio | goomer | menudino | anotaai | cardapioweb | ifood | pdf | imagem | outro
    origem: Mapped[str] = mapped_column(String(30), default="link_site")  # osm_tag | jsonld | link_site
    itens: Mapped[list] = mapped_column(JSON, default=list)  # [{secao, nome, descricao, preco}]
    status: Mapped[str] = mapped_column(String(20), index=True, default="provavel")  # confirmado (jsonld/osm) | provavel (link no site) | rejeitado
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)


class Avaliacao(Base):
    """Avaliação feita por usuários do TURIZ depois de uma experiência registrada (dado próprio).
    Não guardamos notas de terceiros (Google, TripAdvisor...): os termos desses serviços costumam proibir.
    Esta tabela NÃO é exportada para data/ (repositório público): vive só no banco da API."""
    __tablename__ = "avaliacoes"
    __table_args__ = (UniqueConstraint("experiencia_ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lugar_fonte: Mapped[str] = mapped_column(String(30), index=True)
    lugar_fonte_id: Mapped[str] = mapped_column(String(200), index=True)
    experiencia_ref: Mapped[str] = mapped_column(String(80))  # uma nota fiscal = uma experiência = uma avaliação
    autor_ref: Mapped[str] = mapped_column(String(80), default="")  # id opaco do usuário, nunca e-mail/nome
    nota_comida: Mapped[int] = mapped_column(default=0)
    nota_ambiente: Mapped[int] = mapped_column(default=0)
    nota_atendimento: Mapped[int] = mapped_column(default=0)
    comentario: Mapped[str] = mapped_column(Text, default="")
    validada: Mapped[bool] = mapped_column(Boolean, default=False)  # experiência confirmada por nota fiscal
    status: Mapped[str] = mapped_column(String(20), index=True, default="pendente")  # publicada | pendente | rejeitada
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
