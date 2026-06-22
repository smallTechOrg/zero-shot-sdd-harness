import pytest
import duckdb
from pathlib import Path
from dotenv import load_dotenv

# Load .env from repo root so GEMINI_API_KEY is in os.environ for all tests
load_dotenv(Path(__file__).parent.parent / ".env", override=False)


@pytest.fixture(autouse=True)
def _reset_settings_singleton():
    import data_analyst.config.settings as m
    m._settings = None
    yield
    m._settings = None


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Isolated SQLite DB for tests — same driver as production."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from data_analyst.db.models import Base
    import data_analyst.db.session as session_module

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)
    yield engine
    engine.dispose()


@pytest.fixture
def isolated_duckdb(tmp_path):
    """Fresh DuckDB instance for each test."""
    from data_analyst.duckdb_service import DuckDBService
    svc = DuckDBService(str(tmp_path / "test.duckdb"))
    yield svc
    svc._conn.close()
