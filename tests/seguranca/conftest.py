import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./teste.db")
os.environ.setdefault("API_KEY", "k")


@pytest.fixture(autouse=True)
def limpo(monkeypatch):
    """Cada teste começa sem bloqueios e com os limites originais."""
    from app.eventos import api as api_eventos
    from app.seguranca import limites
    guardados = [(l, l.maximo) for l in limites.TODOS]
    limites.reiniciar_todos(); api_eventos._hist.clear()
    yield
    for l, m in guardados:
        l.maximo = m
    limites.reiniciar_todos(); api_eventos._hist.clear()


@pytest.fixture
def cliente():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
