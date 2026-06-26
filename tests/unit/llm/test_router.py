"""Router + cost-tier pricing — deterministic, no LLM key required."""
import pytest

from llm.base import price
from llm.router import Router, get_router, reset_router


def test_route_returns_configured_model_per_task():
    r = Router(classify="m-classify", tools="m-tools", reason="m-reason")
    assert r.route("classify") == "m-classify"
    assert r.route("tools") == "m-tools"
    assert r.route("reason") == "m-reason"


def test_blank_route_falls_back_to_none():
    r = Router()  # all blank
    assert r.route("classify") is None
    assert r.route("tools") is None
    assert r.route("reason") is None


def test_unknown_task_raises():
    with pytest.raises(ValueError):
        Router().route("nonsense")


def test_get_router_reads_settings(monkeypatch):
    monkeypatch.setenv("AGENT_MODEL_TOOLS", "claude-haiku-4-5")
    import config.settings as m
    m._settings = None
    reset_router()
    assert get_router().route("tools") == "claude-haiku-4-5"
    assert get_router().route("reason") is None  # unset → default


def test_price_known_tiers():
    # Haiku 1/5 per Mtok: 1M in + 1M out = 1.00 + 5.00
    assert price("claude-haiku-4-5", 1_000_000, 1_000_000) == pytest.approx(6.00)
    # Sonnet 3/15
    assert price("claude-sonnet-4-6", 1_000_000, 1_000_000) == pytest.approx(18.00)
    # Opus 5/25
    assert price("claude-opus-4-8", 1_000_000, 1_000_000) == pytest.approx(30.00)
    # Gemini Flash 0.15/0.60
    assert price("gemini-2.5-flash", 1_000_000, 1_000_000) == pytest.approx(0.75)


def test_price_prefix_matches_dated_id():
    # A dated/suffixed id resolves to its base tier
    assert price("claude-haiku-4-5-20251001", 1_000_000, 0) == pytest.approx(1.00)


def test_price_unknown_model_is_zero():
    assert price("some-unknown-model", 1_000_000, 1_000_000) == 0.0
