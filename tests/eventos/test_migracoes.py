import os
import tempfile
import pytest
from sqlalchemy import create_engine, inspect, text
import app.migrar as migrar
from app.db import Base


@pytest.fixture
def banco(monkeypatch):
    """Banco SQLite isolado; troca o engine usado pelas migrações."""
    d = tempfile.mkdtemp()
    eng = create_engine(f"sqlite:///{d}/m.db")
    monkeypatch.setattr(migrar, "engine", eng)
    return eng


def _env_engine(monkeypatch, eng):
    import app.db as db
    monkeypatch.setattr(db, "engine", eng)


def rodar(eng, monkeypatch):
    # env.py importa `engine` de app.db no momento da execução: aponta para o banco de teste
    import app.db as db
    monkeypatch.setattr(db, "engine", eng)
    migrar.upgrade_head()


def test_banco_vazio_chega_ao_esquema_do_modelo(monkeypatch, tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/a.db")
    monkeypatch.setattr(migrar, "engine", eng)
    rodar(eng, monkeypatch)
    insp = inspect(eng)
    esperadas = {t.name for t in Base.metadata.sorted_tables}
    assert esperadas <= set(insp.get_table_names())
    # nenhuma coluna do modelo pode faltar no banco migrado (detecta esquecimento de migração)
    for t in Base.metadata.sorted_tables:
        no_banco = {c["name"] for c in insp.get_columns(t.name)}
        assert {c.name for c in t.columns} <= no_banco, f"tabela {t.name}: faltam {sorted({c.name for c in t.columns} - no_banco)}"


def test_banco_antigo_e_atualizado_sem_perder_dados(monkeypatch, tmp_path):
    from alembic import command
    eng = create_engine(f"sqlite:///{tmp_path}/b.db")
    monkeypatch.setattr(migrar, "engine", eng)
    import app.db as db
    monkeypatch.setattr(db, "engine", eng)
    command.upgrade(migrar.config(), "0001")                      # simula o banco como era antes
    with eng.begin() as c:
        c.execute(text("DROP TABLE alembic_version"))               # ...criado por create_all, sem controle de versão
        c.execute(text("INSERT INTO lugares (fonte,fonte_id,tipo,nome,culinaria,endereco,bairro,cep,telefone,site,horario,extra) VALUES "
                       "('osm','node/1','bar','Bar Antigo','','','','','','','','{}')"))
        c.execute(text("INSERT INTO eventos (fonte,fonte_id,titulo,descricao,local_nome,endereco,url,lugar_fonte,lugar_fonte_id,categoria,imagem_url,gratuito,ingresso_url,extra) VALUES "
                       "('site','e1','Show Antigo','','','','','','','musica','',0,'','{}')"))
    migrar.upgrade_head()
    with eng.connect() as c:
        assert c.execute(text("SELECT nome FROM lugares")).scalar() == "Bar Antigo"
        row = c.execute(text("SELECT titulo, status, nome_norm, preco_max FROM eventos")).one()
        assert tuple(row) == ("Show Antigo", "agendado", "", None)   # evento antigo preservado, com padrões
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0002"
    assert "evento_fontes" in inspect(eng).get_table_names()


def test_migracao_e_idempotente_e_reversivel(monkeypatch, tmp_path):
    from alembic import command
    eng = create_engine(f"sqlite:///{tmp_path}/c.db")
    monkeypatch.setattr(migrar, "engine", eng)
    rodar(eng, monkeypatch)
    rodar(eng, monkeypatch)                                       # rodar de novo não faz nada nem quebra
    command.downgrade(migrar.config(), "0001")
    assert "evento_fontes" not in inspect(eng).get_table_names() and "lugares" in inspect(eng).get_table_names()
    assert "status" not in {c["name"] for c in inspect(eng).get_columns("eventos")}
    command.upgrade(migrar.config(), "head")
    assert "evento_fontes" in inspect(eng).get_table_names()
