"""Settings tests — no LLM key required."""
import pytest


def test_defaults(monkeypatch):
    monkeypatch.setenv("AGENT_DATABASE_URL", "sqlite:///./data/test.db")
    from config.settings import get_settings
    s = get_settings()
    assert s.database_url == "sqlite:///./data/test.db"
    assert s.llm_model == "gemini-2.5-flash"


def test_gemini_key_from_env(monkeypatch):
    monkeypatch.setenv("AGENT_GEMINI_API_KEY", "test-key-123")
    from config.settings import get_settings
    s = get_settings()
    assert s.gemini_api_key == "test-key-123"


def test_default_database_url(monkeypatch):
    # Remove any override so we get the real default
    monkeypatch.delenv("AGENT_DATABASE_URL", raising=False)
    from config.settings import get_settings
    s = get_settings()
    assert "sqlite" in s.database_url


def test_log_level_default(monkeypatch):
    monkeypatch.setenv("AGENT_DATABASE_URL", "sqlite:///./data/test.db")
    from config.settings import get_settings
    s = get_settings()
    assert s.log_level == "INFO"
