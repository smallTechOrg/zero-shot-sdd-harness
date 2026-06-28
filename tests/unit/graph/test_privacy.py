"""Privacy boundary test (HARD CONSTRAINT).

Captures the exact prompt strings handed to the LLM in `plan` and
`generate_code` and asserts they contain the schema + the sample rows, but NOT
any full-file data rows beyond the <= 20-row sample.
"""
import graph.nodes as nodes
from llm.client import LLMClient as _RealLLMClient


def _fake_client_factory(provider):
    def _factory():
        c = object.__new__(_RealLLMClient)
        c._provider = provider
        return c
    return _factory


def _state_with_secret_beyond_sample():
    # 20 sample rows the LLM is allowed to see; a 21st "secret" row it must NOT.
    sample = [{"status": "delivered", "customer": f"cust_{i}"} for i in range(20)]
    return {
        "run_id": "priv",
        "question": "How many orders per status?",
        "schema": [
            {"name": "status", "dtype": "object"},
            {"name": "customer", "dtype": "object"},
        ],
        "sample_rows": sample,
        "tokens": 0,
        "error": None,
    }


SECRET_VALUE = "TOP_SECRET_PII_ROW_99441"


def test_plan_prompt_excludes_full_data(monkeypatch):
    captured = {}

    class _Capture:
        def call_model_with_usage(self, prompt, *, system=None):
            captured["prompt"] = prompt
            captured["system"] = system
            return "a plan", 3

    monkeypatch.setattr(nodes, "LLMClient", _fake_client_factory(_Capture()))

    state = _state_with_secret_beyond_sample()
    nodes.plan(state)

    prompt = captured["prompt"]
    # schema present
    assert "status" in prompt and "customer" in prompt
    # sample present
    assert "cust_0" in prompt
    # a value that exists only in the FULL file (never in schema/sample) is absent
    assert SECRET_VALUE not in prompt


def test_code_prompt_excludes_full_data(monkeypatch):
    captured = {}

    class _Capture:
        def call_model_with_usage(self, prompt, *, system=None):
            captured["prompt"] = prompt
            return "```python\nresult = 1\n```", 3

    monkeypatch.setattr(nodes, "LLMClient", _fake_client_factory(_Capture()))

    state = _state_with_secret_beyond_sample()
    state["plan"] = "group and count"
    nodes.generate_code(state)

    prompt = captured["prompt"]
    assert "status" in prompt          # schema
    assert "cust_0" in prompt          # sample
    assert SECRET_VALUE not in prompt  # full-file data never leaks


def test_prompt_builders_only_use_safe_fields():
    """Direct check that the builders read only schema/sample/question/plan/error."""
    state = _state_with_secret_beyond_sample()
    state["plan"] = "p"
    state["last_error"] = "prior boom"
    p = nodes.build_plan_prompt(state)
    c = nodes.build_code_prompt(state)
    assert SECRET_VALUE not in p and SECRET_VALUE not in c
    assert "prior boom" in c  # retry error IS fed back
