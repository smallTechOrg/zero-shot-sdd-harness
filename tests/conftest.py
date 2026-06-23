import pytest
import config.settings as settings_module


@pytest.fixture(autouse=True)
def _reset_settings_singleton():
    settings_module._settings = None
    yield
    settings_module._settings = None


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Use an isolated SQLite DB for each test."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.models import Base
    import db.session as session_module

    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("AGENT_DATABASE_URL", db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)
    yield engine
    engine.dispose()
    session_module._engine = None
    session_module._SessionLocal = None
