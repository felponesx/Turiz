"""Aplica as migrações versionadas (Alembic) no banco configurado em DATABASE_URL.

- banco vazio: executa 0001 e 0002;
- banco antigo (tabelas criadas por create_all, sem alembic_version): marca 0001 como já aplicada e executa as demais;
- nada é apagado: as migrações só acrescentam.
"""
import os
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect
from .db import engine

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def config() -> Config:
    cfg = Config(os.path.join(RAIZ, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(RAIZ, "migracoes"))
    return cfg


def upgrade_head() -> None:
    cfg = config()
    with engine.connect() as c:
        atual = MigrationContext.configure(c).get_current_revision()
        tabelas = set(inspect(c).get_table_names())
    if atual is None and "lugares" in tabelas:
        # banco criado antes das migrações: se já tem as tabelas de eventos v2 (create_all do modelo atual), está em dia
        command.stamp(cfg, "head" if "evento_fontes" in tabelas else "0001")
    command.upgrade(cfg, "head")
