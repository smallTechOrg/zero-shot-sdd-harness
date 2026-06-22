import pytest


@pytest.fixture(autouse=True)
def _reset_settings_singleton():
    import config.settings as m
    m._settings = None
    yield
    m._settings = None


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.models import Base
    import db.session as session_module

    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _isolated_duckdb(tmp_path, monkeypatch):
    """Point the shared DuckDB store at a temp file and reset between tests."""
    import config.settings as settings_module
    import analytics.duckdb_store as store_module

    store_module.reset_connection()
    db_path = str(tmp_path / "analytics.duckdb")

    orig_get = settings_module.get_settings

    def _patched_get():
        s = orig_get()
        object.__setattr__(s, "duckdb_path", db_path)
        return s

    monkeypatch.setattr(settings_module, "get_settings", _patched_get)
    # duckdb_store imports get_settings lazily inside _db_path, so the patch applies
    yield db_path
    store_module.reset_connection()


@pytest.fixture
def _require_llm_key():
    """Skip if no LLM provider key is set — works for Anthropic or Gemini."""
    from config.settings import get_settings
    s = get_settings()
    if not s.anthropic_api_key and not s.gemini_api_key:
        pytest.skip("No LLM key set in .env (AGENT_ANTHROPIC_API_KEY or AGENT_GEMINI_API_KEY)")


@pytest.fixture
def api_client(_isolated_db):
    """FastAPI test client with isolated DB."""
    from fastapi.testclient import TestClient
    from api import app
    with TestClient(app) as client:
        yield client
