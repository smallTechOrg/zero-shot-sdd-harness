import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from data_analyst.db.models import Base
import data_analyst.config.settings as settings_module
import data_analyst.db.session as session_module
import data_analyst.llm.client as llm_module
import data_analyst.duckdb_engine.engine as duckdb_module


@pytest.fixture(autouse=True)
def _reset_settings_singleton():
    """Reset cached settings so env patches take effect in every test."""
    settings_module._settings = None
    yield
    settings_module._settings = None


@pytest.fixture(autouse=True)
def _reset_llm_client():
    llm_module._client = None
    yield
    llm_module._client = None


@pytest.fixture(autouse=True)
def _reset_duckdb():
    """Fresh DuckDB connection per test."""
    duckdb_module.drop_connection()
    yield
    duckdb_module.drop_connection()


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Provide a fresh SQLite DB for each test."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)
    monkeypatch.setenv("ANALYST_DATABASE_URL", db_url)
    monkeypatch.setenv("ANALYST_DATA_DIR", str(tmp_path))
    yield engine
    engine.dispose()


@pytest.fixture()
def client(tmp_db):
    """FastAPI TestClient with fresh DB."""
    from data_analyst.api import create_app
    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
