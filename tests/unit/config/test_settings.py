import pytest
from data_analyst.config.settings import Settings, get_settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("ANALYST_GEMINI_API_KEY", raising=False)
    s = Settings()
    assert s.gemini_api_key == ""
    assert s.token_budget_hard_cap == 32000
    assert s.gemini_llm_model == "gemini-2.5-flash"
    assert s.backend_port == 8001


def test_env_override(monkeypatch):
    monkeypatch.setenv("ANALYST_TOKEN_BUDGET_HARD_CAP", "16000")
    monkeypatch.setenv("ANALYST_GEMINI_LLM_MODEL", "gemini-pro")
    s = Settings()
    assert s.token_budget_hard_cap == 16000
    assert s.gemini_llm_model == "gemini-pro"


def test_extra_ignore(monkeypatch):
    monkeypatch.setenv("ANALYST_UNKNOWN_VAR", "hello")
    s = Settings()  # Should not raise
    assert s is not None


def test_singleton_reset(monkeypatch):
    import data_analyst.config.settings as m
    m._settings = None
    monkeypatch.setenv("ANALYST_BACKEND_PORT", "9999")
    s = get_settings()
    assert s.backend_port == 9999
