"""Tabelas do sistema de eventos (v2). A tabela canônica de eventos continua sendo `eventos` (app/models.py::Evento).

Mapa para os nomes da especificação:  events=eventos | event_sources=evento_fontes (+ evento_fonte_links, uma linha por
anúncio do mesmo evento em cada fonte) | event_categories=evento_categorias (+ evento_categoria_links) | event_locations=
evento_locais | event_images=evento_imagens | event_artists=evento_artistas (+ evento_artista_links) | event_organizers=
evento_organizadores | event_updates=evento_atualizacoes | event_collection_logs=evento_coletas_log. Fila de revisão de
duplicidades: evento_duplicatas.
"""
from datetime import datetime, timezone
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base


def agora():
    return datetime.now(timezone.utc)


class EventoFonte(Base):
    """Cadastro de fontes (conectores configurados). Sem segredos: a chave de API vem de variável de ambiente."""
    __tablename__ = "evento_fontes"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    nome: Mapped[str] = mapped_column(String(200), default="")
    conector: Mapped[str] = mapped_column(String(40))            # ticketmaster | jsonld | feed_json | feed_xml | rss | navegador | planilha | manual
    config: Mapped[dict] = mapped_column(JSON, default=dict)      # url, parâmetros... (nunca credenciais)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    intervalo_horas: Mapped[int] = mapped_column(default=24)
    prioridade: Mapped[int] = mapped_column(default=50)           # maior = vence em conflito de campos
    autorizacao: Mapped[str] = mapped_column(String(20), default="pendente")  # autorizada | pendente | bloqueada | nao_requer
    saude: Mapped[str] = mapped_column(String(30), default="nunca_executada", index=True)  # ok | erro | aguardando_credencial | bloqueada | desativada | nunca_executada
    ultima_execucao_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ultimo_sucesso_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ultimo_erro: Mapped[str] = mapped_column(String(500), default="")
    origem: Mapped[str] = mapped_column(String(20), default="arquivo")  # arquivo (fontes_eventos.yml) | admin
    organizador_id: Mapped[int | None] = mapped_column(nullable=True)
    observacao: Mapped[str] = mapped_column(String(500), default="")


class EventoFonteLink(Base):
    """Cada anúncio de um evento em cada fonte. O mesmo evento pode ter vários (Ticketmaster, Ticket360...)."""
    __tablename__ = "evento_fonte_links"
    __table_args__ = (UniqueConstraint("fonte", "fonte_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"), index=True)
    fonte: Mapped[str] = mapped_column(String(60), index=True)    # slug da fonte
    fonte_id: Mapped[str] = mapped_column(String(200))
    plataforma: Mapped[str] = mapped_column(String(60), default="")  # origem dentro da fonte (ex.: ticketmaster | universe | frontgate | tmr)
    url: Mapped[str] = mapped_column(String(600), default="")
    ingresso_url: Mapped[str] = mapped_column(String(600), default="")
    coletado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    visto_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    dados: Mapped[dict] = mapped_column(JSON, default=dict)       # campos como a fonte informou (preço, status bruto...)


class EventoLocal(Base):
    __tablename__ = "evento_locais"
    __table_args__ = (UniqueConstraint("fonte", "fonte_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(300), default="")
    nome_norm: Mapped[str] = mapped_column(String(300), default="", index=True)
    endereco: Mapped[str] = mapped_column(String(400), default="")
    cidade: Mapped[str] = mapped_column(String(120), default="", index=True)
    estado: Mapped[str] = mapped_column(String(60), default="")
    pais: Mapped[str] = mapped_column(String(60), default="", index=True)
    cep: Mapped[str] = mapped_column(String(20), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    fonte: Mapped[str] = mapped_column(String(60), default="")
    fonte_id: Mapped[str] = mapped_column(String(200), default="")  # id do local na fonte (vazio = sem id)
    lugar_fonte: Mapped[str] = mapped_column(String(30), default="")  # vínculo com restaurante/bar de `lugares`
    lugar_fonte_id: Mapped[str] = mapped_column(String(200), default="", index=True)


class EventoImagem(Base):
    __tablename__ = "evento_imagens"
    __table_args__ = (UniqueConstraint("evento_id", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"), index=True)
    url: Mapped[str] = mapped_column(String(600))
    largura: Mapped[int | None] = mapped_column(nullable=True)
    altura: Mapped[int | None] = mapped_column(nullable=True)
    proporcao: Mapped[str] = mapped_column(String(10), default="")
    tipo: Mapped[str] = mapped_column(String(20), default="principal")  # principal | galeria | artista
    fallback: Mapped[bool] = mapped_column(Boolean, default=False)      # imagem genérica da fonte (não é foto do evento)
    fonte: Mapped[str] = mapped_column(String(60), default="")
    credito: Mapped[str] = mapped_column(String(200), default="")


class EventoArtista(Base):
    __tablename__ = "evento_artistas"
    __table_args__ = (UniqueConstraint("fonte", "fonte_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(300))
    nome_norm: Mapped[str] = mapped_column(String(300), index=True, default="")
    fonte: Mapped[str] = mapped_column(String(60), default="")
    fonte_id: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(String(600), default="")
    imagem_url: Mapped[str] = mapped_column(String(600), default="")


class EventoArtistaLink(Base):
    __tablename__ = "evento_artista_links"
    __table_args__ = (UniqueConstraint("evento_id", "artista_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"), index=True)
    artista_id: Mapped[int] = mapped_column(ForeignKey("evento_artistas.id"), index=True)
    ordem: Mapped[int] = mapped_column(default=0)


class EventoOrganizador(Base):
    """Organizador/promotor/produtora/casa parceira. Só dados comerciais públicos: nada de contato pessoal."""
    __tablename__ = "evento_organizadores"
    __table_args__ = (UniqueConstraint("fonte", "fonte_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(300))
    nome_norm: Mapped[str] = mapped_column(String(300), index=True, default="")
    tipo: Mapped[str] = mapped_column(String(20), default="organizador")  # organizador | promotor | produtora | casa | estabelecimento
    fonte: Mapped[str] = mapped_column(String(60), default="")
    fonte_id: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(String(600), default="")
    parceiro: Mapped[bool] = mapped_column(Boolean, default=False)       # cadastrado/autorizado diretamente
    observacao: Mapped[str] = mapped_column(String(500), default="")


class EventoCategoria(Base):
    __tablename__ = "evento_categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    grupo: Mapped[str] = mapped_column(String(40), index=True)           # musica | gastronomia | cultura
    pai_id: Mapped[int | None] = mapped_column(ForeignKey("evento_categorias.id"), nullable=True)
    ordem: Mapped[int] = mapped_column(default=0)


class EventoCategoriaLink(Base):
    __tablename__ = "evento_categoria_links"
    __table_args__ = (UniqueConstraint("evento_id", "categoria_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"), index=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("evento_categorias.id"), index=True)
    primaria: Mapped[bool] = mapped_column(Boolean, default=False)
    origem: Mapped[str] = mapped_column(String(20), default="fonte")      # fonte | regra | manual


class EventoAtualizacao(Base):
    """Histórico: cada mudança relevante de um evento (nunca apagamos cancelados/vencidos)."""
    __tablename__ = "evento_atualizacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"), index=True)
    quando: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)
    fonte: Mapped[str] = mapped_column(String(60), default="")
    tipo: Mapped[str] = mapped_column(String(20), default="alterado")     # criado | alterado | status | mesclado
    campo: Mapped[str] = mapped_column(String(60), default="")
    valor_antigo: Mapped[str] = mapped_column(String(500), default="")
    valor_novo: Mapped[str] = mapped_column(String(500), default="")


class EventoColetaLog(Base):
    __tablename__ = "evento_coletas_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    fonte: Mapped[str] = mapped_column(String(60), index=True)
    iniciado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)
    terminado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="em_andamento")  # sucesso | parcial | erro | aguardando_credencial | bloqueada | ignorada
    paginas: Mapped[int] = mapped_column(default=0)
    coletados: Mapped[int] = mapped_column(default=0)
    novos: Mapped[int] = mapped_column(default=0)
    atualizados: Mapped[int] = mapped_column(default=0)
    duplicados: Mapped[int] = mapped_column(default=0)
    revisao: Mapped[int] = mapped_column(default=0)
    descartados: Mapped[int] = mapped_column(default=0)
    erros: Mapped[int] = mapped_column(default=0)
    mensagem: Mapped[str] = mapped_column(String(500), default="")        # sempre sem segredos


class EventoDuplicata(Base):
    """Fila de revisão: pares que parecem o mesmo evento, mas sem certeza suficiente para mesclar sozinho."""
    __tablename__ = "evento_duplicatas"
    __table_args__ = (UniqueConstraint("evento_a_id", "evento_b_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_a_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"), index=True)
    evento_b_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    motivos: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pendente", index=True)  # pendente | mesclado | distinto
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
