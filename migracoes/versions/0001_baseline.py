"""baseline: tabelas que já existiam antes das migrações (criadas por create_all)

Em bancos antigos (que já têm essas tabelas) a aplicação faz `stamp 0001` em vez de executar esta migração.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _dt():
    return sa.DateTime(timezone=True)


def upgrade():
    op.create_table("lugares",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("fonte", sa.String(30)), sa.Column("fonte_id", sa.String(200)),
        sa.Column("tipo", sa.String(20)), sa.Column("nome", sa.String(300)), sa.Column("culinaria", sa.String(200)),
        sa.Column("lat", sa.Float, nullable=True), sa.Column("lon", sa.Float, nullable=True), sa.Column("endereco", sa.String(400)),
        sa.Column("bairro", sa.String(120)), sa.Column("cep", sa.String(20)), sa.Column("telefone", sa.String(80)),
        sa.Column("site", sa.String(400)), sa.Column("horario", sa.String(400)), sa.Column("nota", sa.Float, nullable=True),
        sa.Column("extra", sa.JSON), sa.Column("atualizado_em", _dt()), sa.UniqueConstraint("fonte", "fonte_id"))
    for c in ("fonte", "tipo", "nome", "bairro"):
        op.create_index(f"ix_lugares_{c}", "lugares", [c])
    op.create_table("eventos",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("fonte", sa.String(30)), sa.Column("fonte_id", sa.String(200)),
        sa.Column("titulo", sa.String(400)), sa.Column("descricao", sa.Text), sa.Column("inicio", _dt(), nullable=True),
        sa.Column("fim", _dt(), nullable=True), sa.Column("local_nome", sa.String(300)), sa.Column("endereco", sa.String(400)),
        sa.Column("lat", sa.Float, nullable=True), sa.Column("lon", sa.Float, nullable=True), sa.Column("url", sa.String(500)),
        sa.Column("lugar_fonte", sa.String(30)), sa.Column("lugar_fonte_id", sa.String(200)), sa.Column("categoria", sa.String(60)),
        sa.Column("imagem_url", sa.String(600)), sa.Column("preco_min", sa.Float, nullable=True), sa.Column("gratuito", sa.Boolean),
        sa.Column("ingresso_url", sa.String(600)), sa.Column("extra", sa.JSON), sa.Column("atualizado_em", _dt()),
        sa.UniqueConstraint("fonte", "fonte_id"))
    for c in ("fonte", "titulo", "inicio", "lugar_fonte", "lugar_fonte_id", "categoria"):
        op.create_index(f"ix_eventos_{c}", "eventos", [c])
    op.create_table("imagens",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("lugar_fonte", sa.String(30)), sa.Column("lugar_fonte_id", sa.String(200)),
        sa.Column("fonte", sa.String(30)), sa.Column("url", sa.String(600)), sa.Column("thumb_url", sa.String(600)),
        sa.Column("largura", sa.Integer, nullable=True), sa.Column("altura", sa.Integer, nullable=True), sa.Column("licenca", sa.String(120)),
        sa.Column("autor", sa.String(300)), sa.Column("creditos_url", sa.String(600)), sa.Column("status", sa.String(20)),
        sa.Column("atualizado_em", _dt()), sa.UniqueConstraint("lugar_fonte", "lugar_fonte_id", "url"))
    for c in ("lugar_fonte", "lugar_fonte_id", "fonte", "status"):
        op.create_index(f"ix_imagens_{c}", "imagens", [c])
    op.create_table("redes_sociais",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("lugar_fonte", sa.String(30)), sa.Column("lugar_fonte_id", sa.String(200)),
        sa.Column("rede", sa.String(20)), sa.Column("usuario", sa.String(60)), sa.Column("url", sa.String(200)), sa.Column("origem", sa.String(30)),
        sa.Column("confianca", sa.Float), sa.Column("status", sa.String(20)), sa.Column("nome_perfil", sa.String(200)),
        sa.Column("seguidores", sa.Integer, nullable=True), sa.Column("extra", sa.JSON), sa.Column("atualizado_em", _dt()),
        sa.UniqueConstraint("lugar_fonte", "lugar_fonte_id", "rede", "usuario"))
    for c in ("lugar_fonte", "lugar_fonte_id", "status"):
        op.create_index(f"ix_redes_sociais_{c}", "redes_sociais", [c])
    op.create_table("cardapios",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("lugar_fonte", sa.String(30)), sa.Column("lugar_fonte_id", sa.String(200)),
        sa.Column("url", sa.String(600)), sa.Column("plataforma", sa.String(30)), sa.Column("origem", sa.String(30)), sa.Column("itens", sa.JSON),
        sa.Column("status", sa.String(20)), sa.Column("atualizado_em", _dt()), sa.UniqueConstraint("lugar_fonte", "lugar_fonte_id", "url"))
    for c in ("lugar_fonte", "lugar_fonte_id", "status"):
        op.create_index(f"ix_cardapios_{c}", "cardapios", [c])
    op.create_table("avaliacoes",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("lugar_fonte", sa.String(30)), sa.Column("lugar_fonte_id", sa.String(200)),
        sa.Column("experiencia_ref", sa.String(80)), sa.Column("autor_ref", sa.String(80)), sa.Column("nota_comida", sa.Integer),
        sa.Column("nota_ambiente", sa.Integer), sa.Column("nota_atendimento", sa.Integer), sa.Column("comentario", sa.Text),
        sa.Column("validada", sa.Boolean), sa.Column("status", sa.String(20)), sa.Column("criado_em", _dt()), sa.UniqueConstraint("experiencia_ref"))
    for c in ("lugar_fonte", "lugar_fonte_id", "status"):
        op.create_index(f"ix_avaliacoes_{c}", "avaliacoes", [c])


def downgrade():
    for t in ("avaliacoes", "cardapios", "redes_sociais", "imagens", "eventos", "lugares"):
        op.drop_table(t)
