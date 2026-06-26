"""Phase 1 gate — routing drives a real per-call model choice, priced at the
routed tier. Real LLM via .env (single configured provider).
"""
import pytest
from sqlalchemy.orm import Session

from llm.base import price
from db import session as session_module
from db.models import RunRow


@pytest.mark.usefixtures("_require_llm_key")
def test_routed_model_is_used_and_priced_at_its_tier(_isolated_db, monkeypatch):
    """Setting AGENT_MODEL_TOOLS to a specific tier routes the capability call
    to that model AND prices it at that model's tier — not the provider default.
    """
    from config.settings import get_settings
    import config.settings as settings_mod
    import llm.router as router_mod

    s0 = get_settings()
    # Pick a concrete tier id for whichever provider is configured.
    if s0.anthropic_api_key:
        routed = "claude-haiku-4-5"
    else:
        routed = "gemini-2.5-flash"

    monkeypatch.setenv("AGENT_MODEL_TOOLS", routed)
    settings_mod._settings = None
    router_mod.reset_router()

    from graph.runner import run_agent
    run_id = run_agent("Reply with the single word: ok.")

    with Session(session_module._engine) as sess:
        run = sess.get(RunRow, run_id)

    assert run.status == "completed", run.error_message
    assert run.error_message is None
    # The routed model was actually used (prefix-match tolerates dated ids).
    assert run.model.startswith(routed), f"expected {routed}, got {run.model}"
    # And cost was computed at the ROUTED tier, not Sonnet/Flash default.
    expected = price(run.model, run.tokens_in, run.tokens_out)
    assert run.cost_usd == pytest.approx(expected, rel=1e-6)
    assert run.cost_usd > 0


@pytest.mark.usefixtures("_require_llm_key")
def test_blank_route_uses_provider_default(_isolated_db):
    """With no routing set, behaviour is unchanged — provider default model."""
    from graph.runner import run_agent
    run_id = run_agent("Reply with the single word: ok.")
    with Session(session_module._engine) as sess:
        run = sess.get(RunRow, run_id)
    assert run.status == "completed", run.error_message
    assert run.model  # some default model id was recorded
    assert run.cost_usd >= 0
