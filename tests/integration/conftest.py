import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import data_analyst.config.settings as settings_module
import data_analyst.db.session as session_module
from data_analyst.db.models import Base


@pytest.fixture(autouse=True)
def _stub_env(tmp_path, monkeypatch):
    """No Gemini key -> stub provider. Isolated SQLite metadata + DuckDB per test."""
    monkeypatch.setenv("DATA_ANALYST_GEMINI_API_KEY", "")
    monkeypatch.setenv("DATA_ANALYST_LLM_PROVIDER", "auto")
    monkeypatch.setenv("DATA_ANALYST_DUCKDB_PATH", str(tmp_path / "datasets.duckdb"))
    settings_module._settings = None

    db_url = f"sqlite:///{tmp_path}/metadata.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    session_module._apply_sqlite_pragmas(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)
    yield
    engine.dispose()
    settings_module._settings = None
