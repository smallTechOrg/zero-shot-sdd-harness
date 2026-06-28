"""Conditional-edge routing tests — pure logic, no LLM."""
from graph.edges import after_plan, after_generate_code, after_execute


def test_after_plan_ok():
    assert after_plan({"error": None}) == "generate_code"


def test_after_plan_error():
    assert after_plan({"error": "boom"}) == "handle_error"


def test_after_generate_code_ok():
    assert after_generate_code({"error": None}) == "execute_code"


def test_after_generate_code_error():
    assert after_generate_code({"error": "boom"}) == "handle_error"


def test_after_execute_success_finalizes():
    state = {"attempts": [{"ok": True}], "retries": 0, "max_retries": 3}
    assert after_execute(state) == "finalize"


def test_after_execute_failure_under_cap_retries():
    state = {"attempts": [{"ok": False}], "retries": 1, "max_retries": 3}
    assert after_execute(state) == "generate_code"


def test_after_execute_failure_at_cap_handles_error():
    state = {"attempts": [{"ok": False}], "retries": 3, "max_retries": 3}
    assert after_execute(state) == "handle_error"
