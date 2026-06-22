from contextlib import contextmanager
from collections.abc import Generator
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        from data_analyst.config.settings import get_settings
        settings = get_settings()
        url = settings.absolute_database_url
        # Ensure data dir exists
        import re
        m = re.match(r"sqlite:///(.+)", url)
        if m:
            from pathlib import Path
            Path(m.group(1)).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})
    return _engine


def _get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency."""
    factory = _get_session_factory()
    with factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


@contextmanager
def create_db_session() -> Generator[Session, None, None]:
    """Standalone context manager."""
    factory = _get_session_factory()
    with factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def init_db() -> None:
    from data_analyst.db.models import Base
    from pathlib import Path
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
