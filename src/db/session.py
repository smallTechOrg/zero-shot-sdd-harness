from contextlib import contextmanager
from collections.abc import Generator

from sqlalchemy import create_engine, Engine, event
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        from config.settings import get_settings
        url = get_settings().database_url
        _engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})

        @event.listens_for(_engine, "connect")
        def set_fk(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return _engine


def _get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency."""
    with _get_session_factory()() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


@contextmanager
def create_db_session() -> Generator[Session, None, None]:
    """Standalone — for graph nodes, CLI, scripts."""
    with _get_session_factory()() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def init_db() -> None:
    from db.models import Base
    Base.metadata.create_all(bind=_get_engine())


def reset_engine() -> None:
    """For tests — resets singletons so monkeypatch takes effect."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
