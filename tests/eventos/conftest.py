import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./teste.db")
os.environ.setdefault("API_KEY", "k")
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base


@pytest.fixture
def db(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()
