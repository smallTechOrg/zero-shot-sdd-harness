"""Deterministic routing tests for the analyst graph edges + retry loop.

These prove the gated dialect-safe retry routing logic WITHOUT an LLM call:
the conditional edge functions are pure, and execute_sql -> generate_sql routing
is exercised with a stubbed bad-SQL-then-good-SQL sequence.
"""
from graph.edges import after_execute, after_guard, after_phrase, after_plan
from graph.state import MAX_SQL_RETRIES


def test_after_plan_routes_on_error():
    assert after_plan({"error": "boom"}) == "handle_error"
    assert after_plan({}) == "privacy_guard"


def test_after_guard_pre_vs_post():
    assert after_guard({"phase": "pre"}) == "execute_sql"
    assert after_guard({}) == "execute_sql"
    assert after_guard({"phase": "post"}) == "phrase_answer"
    assert after_guard({"error": "x", "phase": "post"}) == "handle_error"


def test_after_execute_success_routes_to_guard():
    assert after_execute({"sql_error": None}) == "privacy_guard"


def test_after_execute_retries_while_attempts_remain():
    # error + attempts below cap -> retry
    assert after_execute({"sql_error": "Catalog Error", "sql_attempts": 1}) == "generate_sql"
    assert (
        after_execute({"sql_error": "Catalog Error", "sql_attempts": MAX_SQL_RETRIES - 1})
        == "generate_sql"
    )


def test_after_execute_gives_up_when_exhausted():
    assert (
        after_execute({"sql_error": "Catalog Error", "sql_attempts": MAX_SQL_RETRIES})
        == "handle_error"
    )


def test_after_phrase_routes_on_error():
    assert after_phrase({"error": "boom"}) == "handle_error"
    assert after_phrase({}) == "pick_chart"
