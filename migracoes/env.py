"""Alembic usando o mesmo engine da aplicação (DATABASE_URL). As migrações são escritas à mão e versionadas."""
from alembic import context
from app.db import engine


def run_migrations_online():
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
