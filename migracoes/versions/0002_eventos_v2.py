"""sistema de eventos v2: colunas novas em `eventos` e tabelas evento_*

Só ACRESCENTA: nenhum dado existente é apagado ou alterado.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _dt():
    return sa.DateTime(timezone=True)


def upgrade():
    # --- eventos: novas colunas (todas com valor padrão ou nulas)
    with op.batch_alter_table("eventos") as b:
        b.add_column(sa.Column("nome_norm", sa.String(400), nullable=False, server_default=""))
        b.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="agendado"))
        b.add_column(sa.Column("fuso", sa.String(60), nullable=False, server_default=""))
        b.add_column(sa.Column("data_incerta", sa.Boolean, nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("preco_max", sa.Float, nullable=True))
        b.add_column(sa.Column("moeda", sa.String(8), nullable=False, server_default=""))
        b.add_column(sa.Column("classificacao_indicativa", sa.String(40), nullable=False, server_default=""))
        b.add_column(sa.Column("acessibilidade", sa.Text, nullable=False, server_default=""))
        b.add_column(sa.Column("url_oficial", sa.String(600), nullable=False, server_default=""))
        b.add_column(sa.Column("local_id", sa.Integer, nullable=True))
        b.add_column(sa.Column("organizador_id", sa.Integer, nullable=True))
        b.add_column(sa.Column("coletado_em", _dt(), nullable=True))
        b.add_column(sa.Column("visto_em", _dt(), nullable=True))
    for c in ("nome_norm", "status", "local_id", "organizador_id"):
        op.create_index(f"ix_eventos_{c}", "eventos", [c])

    op.create_table("evento_fontes",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("slug", sa.String(60), nullable=False, unique=True),
        sa.Column("nome", sa.String(200)), sa.Column("conector", sa.String(40), nullable=False), sa.Column("config", sa.JSON),
        sa.Column("ativo", sa.Boolean), sa.Column("intervalo_horas", sa.Integer), sa.Column("prioridade", sa.Integer),
        sa.Column("autorizacao", sa.String(20)), sa.Column("saude", sa.String(30)), sa.Column("ultima_execucao_em", _dt(), nullable=True),
        sa.Column("ultimo_sucesso_em", _dt(), nullable=True), sa.Column("ultimo_erro", sa.String(500)), sa.Column("origem", sa.String(20)),
        sa.Column("organizador_id", sa.Integer, nullable=True), sa.Column("observacao", sa.String(500)))
    op.create_index("ix_evento_fontes_saude", "evento_fontes", ["saude"])

    op.create_table("evento_locais",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("nome", sa.String(300)), sa.Column("nome_norm", sa.String(300)),
        sa.Column("endereco", sa.String(400)), sa.Column("cidade", sa.String(120)), sa.Column("estado", sa.String(60)),
        sa.Column("pais", sa.String(60)), sa.Column("cep", sa.String(20)), sa.Column("lat", sa.Float, nullable=True),
        sa.Column("lon", sa.Float, nullable=True), sa.Column("fonte", sa.String(60)), sa.Column("fonte_id", sa.String(200)),
        sa.Column("lugar_fonte", sa.String(30)), sa.Column("lugar_fonte_id", sa.String(200)), sa.UniqueConstraint("fonte", "fonte_id"))
    for c in ("nome_norm", "cidade", "pais", "lugar_fonte_id"):
        op.create_index(f"ix_evento_locais_{c}", "evento_locais", [c])

    op.create_table("evento_organizadores",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("nome", sa.String(300), nullable=False), sa.Column("nome_norm", sa.String(300)),
        sa.Column("tipo", sa.String(20)), sa.Column("fonte", sa.String(60)), sa.Column("fonte_id", sa.String(200)), sa.Column("url", sa.String(600)),
        sa.Column("parceiro", sa.Boolean), sa.Column("observacao", sa.String(500)), sa.UniqueConstraint("fonte", "fonte_id"))
    op.create_index("ix_evento_organizadores_nome_norm", "evento_organizadores", ["nome_norm"])

    op.create_table("evento_artistas",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("nome", sa.String(300), nullable=False), sa.Column("nome_norm", sa.String(300)),
        sa.Column("fonte", sa.String(60)), sa.Column("fonte_id", sa.String(200)), sa.Column("url", sa.String(600)), sa.Column("imagem_url", sa.String(600)),
        sa.UniqueConstraint("fonte", "fonte_id"))
    op.create_index("ix_evento_artistas_nome_norm", "evento_artistas", ["nome_norm"])

    op.create_table("evento_categorias",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("slug", sa.String(60), nullable=False, unique=True),
        sa.Column("nome", sa.String(120), nullable=False), sa.Column("grupo", sa.String(40), nullable=False),
        sa.Column("pai_id", sa.Integer, sa.ForeignKey("evento_categorias.id"), nullable=True), sa.Column("ordem", sa.Integer))
    op.create_index("ix_evento_categorias_grupo", "evento_categorias", ["grupo"])

    op.create_table("evento_fonte_links",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("evento_id", sa.Integer, sa.ForeignKey("eventos.id"), nullable=False),
        sa.Column("fonte", sa.String(60), nullable=False), sa.Column("fonte_id", sa.String(200), nullable=False), sa.Column("plataforma", sa.String(60)),
        sa.Column("url", sa.String(600)), sa.Column("ingresso_url", sa.String(600)), sa.Column("coletado_em", _dt()), sa.Column("visto_em", _dt()),
        sa.Column("dados", sa.JSON), sa.UniqueConstraint("fonte", "fonte_id"))
    op.create_index("ix_evento_fonte_links_evento_id", "evento_fonte_links", ["evento_id"])
    op.create_index("ix_evento_fonte_links_fonte", "evento_fonte_links", ["fonte"])

    op.create_table("evento_imagens",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("evento_id", sa.Integer, sa.ForeignKey("eventos.id"), nullable=False),
        sa.Column("url", sa.String(600), nullable=False), sa.Column("largura", sa.Integer, nullable=True), sa.Column("altura", sa.Integer, nullable=True),
        sa.Column("proporcao", sa.String(10)), sa.Column("tipo", sa.String(20)), sa.Column("fallback", sa.Boolean), sa.Column("fonte", sa.String(60)),
        sa.Column("credito", sa.String(200)), sa.UniqueConstraint("evento_id", "url"))
    op.create_index("ix_evento_imagens_evento_id", "evento_imagens", ["evento_id"])

    op.create_table("evento_artista_links",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("evento_id", sa.Integer, sa.ForeignKey("eventos.id"), nullable=False),
        sa.Column("artista_id", sa.Integer, sa.ForeignKey("evento_artistas.id"), nullable=False), sa.Column("ordem", sa.Integer),
        sa.UniqueConstraint("evento_id", "artista_id"))
    op.create_index("ix_evento_artista_links_evento_id", "evento_artista_links", ["evento_id"])
    op.create_index("ix_evento_artista_links_artista_id", "evento_artista_links", ["artista_id"])

    op.create_table("evento_categoria_links",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("evento_id", sa.Integer, sa.ForeignKey("eventos.id"), nullable=False),
        sa.Column("categoria_id", sa.Integer, sa.ForeignKey("evento_categorias.id"), nullable=False), sa.Column("primaria", sa.Boolean),
        sa.Column("origem", sa.String(20)), sa.UniqueConstraint("evento_id", "categoria_id"))
    op.create_index("ix_evento_categoria_links_evento_id", "evento_categoria_links", ["evento_id"])
    op.create_index("ix_evento_categoria_links_categoria_id", "evento_categoria_links", ["categoria_id"])

    op.create_table("evento_atualizacoes",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("evento_id", sa.Integer, sa.ForeignKey("eventos.id"), nullable=False),
        sa.Column("quando", _dt()), sa.Column("fonte", sa.String(60)), sa.Column("tipo", sa.String(20)), sa.Column("campo", sa.String(60)),
        sa.Column("valor_antigo", sa.String(500)), sa.Column("valor_novo", sa.String(500)))
    op.create_index("ix_evento_atualizacoes_evento_id", "evento_atualizacoes", ["evento_id"])
    op.create_index("ix_evento_atualizacoes_quando", "evento_atualizacoes", ["quando"])

    op.create_table("evento_coletas_log",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("fonte", sa.String(60), nullable=False), sa.Column("iniciado_em", _dt()),
        sa.Column("terminado_em", _dt(), nullable=True), sa.Column("status", sa.String(30)), sa.Column("paginas", sa.Integer),
        sa.Column("coletados", sa.Integer), sa.Column("novos", sa.Integer), sa.Column("atualizados", sa.Integer), sa.Column("duplicados", sa.Integer),
        sa.Column("revisao", sa.Integer), sa.Column("descartados", sa.Integer), sa.Column("erros", sa.Integer), sa.Column("mensagem", sa.String(500)))
    op.create_index("ix_evento_coletas_log_fonte", "evento_coletas_log", ["fonte"])
    op.create_index("ix_evento_coletas_log_iniciado_em", "evento_coletas_log", ["iniciado_em"])

    op.create_table("evento_duplicatas",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("evento_a_id", sa.Integer, sa.ForeignKey("eventos.id"), nullable=False),
        sa.Column("evento_b_id", sa.Integer, sa.ForeignKey("eventos.id"), nullable=False), sa.Column("score", sa.Float), sa.Column("motivos", sa.JSON),
        sa.Column("status", sa.String(20)), sa.Column("criado_em", _dt()), sa.Column("resolvido_em", _dt(), nullable=True),
        sa.UniqueConstraint("evento_a_id", "evento_b_id"))
    op.create_index("ix_evento_duplicatas_evento_a_id", "evento_duplicatas", ["evento_a_id"])
    op.create_index("ix_evento_duplicatas_evento_b_id", "evento_duplicatas", ["evento_b_id"])
    op.create_index("ix_evento_duplicatas_status", "evento_duplicatas", ["status"])


def downgrade():
    for t in ("evento_duplicatas", "evento_coletas_log", "evento_atualizacoes", "evento_categoria_links", "evento_artista_links",
              "evento_imagens", "evento_fonte_links", "evento_categorias", "evento_artistas", "evento_organizadores", "evento_locais", "evento_fontes"):
        op.drop_table(t)
    for c in ("organizador_id", "local_id", "status", "nome_norm"):
        op.drop_index(f"ix_eventos_{c}", table_name="eventos")
    with op.batch_alter_table("eventos") as b:
        for c in ("visto_em", "coletado_em", "organizador_id", "local_id", "url_oficial", "acessibilidade", "classificacao_indicativa", "moeda",
                  "preco_max", "data_incerta", "fuso", "status", "nome_norm"):
            b.drop_column(c)
