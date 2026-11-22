"""segurança: auditoria, contas de usuário, sessões, tokens e favoritos

Só ACRESCENTA tabelas novas; nenhum dado existente é alterado.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _dt():
    return sa.DateTime(timezone=True)


def upgrade():
    op.create_table("auditoria",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("quando", _dt(), nullable=False),
        sa.Column("ator", sa.String(60), nullable=False, server_default=""), sa.Column("escopo", sa.String(30), nullable=False, server_default=""),
        sa.Column("metodo", sa.String(8), nullable=False, server_default=""), sa.Column("rota", sa.String(200), nullable=False, server_default=""),
        sa.Column("resultado", sa.String(16), nullable=False, server_default=""), sa.Column("ip_hash", sa.String(24), nullable=False, server_default=""),
        sa.Column("request_id", sa.String(32), nullable=False, server_default=""), sa.Column("detalhe", sa.String(300), nullable=False, server_default=""))
    op.create_index("ix_auditoria_quando", "auditoria", ["quando"])
    op.create_index("ix_auditoria_ator", "auditoria", ["ator"])
    op.create_index("ix_auditoria_resultado", "auditoria", ["resultado"])

    op.create_table("usuarios",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("email_norm", sa.String(254), nullable=False),
        sa.Column("email_verificado", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("email_pendente", sa.String(254), nullable=False, server_default=""),
        sa.Column("senha_hash", sa.String(255), nullable=False), sa.Column("nome", sa.String(80), nullable=False, server_default=""),
        sa.Column("papel", sa.String(12), nullable=False, server_default="usuario"), sa.Column("mfa_ativo", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("mfa_segredo", sa.String(255), nullable=False, server_default=""), sa.Column("mfa_recuperacao", sa.JSON, nullable=False),
        sa.Column("falhas_login", sa.Integer, nullable=False, server_default="0"), sa.Column("bloqueado_ate", _dt(), nullable=True),
        sa.Column("ultimo_login_em", _dt(), nullable=True), sa.Column("criado_em", _dt(), nullable=False), sa.Column("atualizado_em", _dt(), nullable=False))
    op.create_index("ix_usuarios_email_norm", "usuarios", ["email_norm"], unique=True)

    op.create_table("sessoes",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False), sa.Column("criado_em", _dt(), nullable=False),
        sa.Column("ultimo_uso_em", _dt(), nullable=False), sa.Column("expira_em", _dt(), nullable=False), sa.Column("revogada_em", _dt(), nullable=True),
        sa.Column("dispositivo", sa.String(120), nullable=False, server_default=""), sa.Column("ip_hash", sa.String(24), nullable=False, server_default=""),
        sa.Column("mfa_ok", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("reauth_em", _dt(), nullable=True))
    op.create_index("ix_sessoes_token_hash", "sessoes", ["token_hash"], unique=True)
    op.create_index("ix_sessoes_usuario_id", "sessoes", ["usuario_id"])

    op.create_table("tokens_conta",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("alvo", sa.String(254), nullable=False, server_default=""), sa.Column("criado_em", _dt(), nullable=False),
        sa.Column("expira_em", _dt(), nullable=False), sa.Column("usado_em", _dt(), nullable=True))
    op.create_index("ix_tokens_conta_token_hash", "tokens_conta", ["token_hash"], unique=True)
    op.create_index("ix_tokens_conta_usuario_id", "tokens_conta", ["usuario_id"])

    op.create_table("favoritos_usuario",
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("tipo", sa.String(12), nullable=False), sa.Column("ref", sa.String(100), nullable=False), sa.Column("criado_em", _dt(), nullable=False),
        sa.UniqueConstraint("usuario_id", "tipo", "ref"))
    op.create_index("ix_favoritos_usuario_usuario_id", "favoritos_usuario", ["usuario_id"])


def downgrade():
    for t in ("favoritos_usuario", "tokens_conta", "sessoes", "usuarios", "auditoria"):
        op.drop_table(t)
