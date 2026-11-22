import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./teste.db")
os.environ.setdefault("API_KEY", "k")


@pytest.fixture(autouse=True)
def limpo(monkeypatch):
    """Cada teste começa sem bloqueios e com os limites originais."""
    from app.seguranca import limites
    guardados = [(l, l.maximo) for l in limites.TODOS]
    limites.reiniciar_todos()
    yield
    for l, m in guardados:
        l.maximo = m
    limites.reiniciar_todos()


@pytest.fixture
def cliente():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
