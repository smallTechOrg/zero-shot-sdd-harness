import pytest


@pytest.fixture(autouse=True)
def _reset_settings_singleton():
    """Reset cached settings singleton so env patches take effect in every test."""
    import datachat.config.settings as m
    m._settings = None
    m._gemini_settings = None
    yield
    m._settings = None
    m._gemini_settings = None


@pytest.fixture(autouse=True)
def _reset_db_singletons():
    """Reset DB engine/session singletons so test DB fixtures take effect."""
    import datachat.db.session as s
    s._engine = None
    s._SessionLocal = None
    yield
    if s._engine is not None:
        s._engine.dispose()
    s._engine = None
    s._SessionLocal = None
