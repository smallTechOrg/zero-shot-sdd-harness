"""Retry-loop test: a first bad code attempt is fed back and corrected.

Uses a deterministic fake LLM (bad code then good code) so this runs without a
real key and proves the reflection/retry mechanism end-to-end through the graph.
"""
import textwrap

import pytest

import graph.nodes as nodes
from llm.client import LLMClient as _RealLLMClient


def _make_fake_client_factory(provider):
    def _factory():
        client = object.__new__(_RealLLMClient)
        client._provider = provider
        return client
    return _factory


@pytest.fixture
def tiny_csv(tmp_path):
    p = tmp_path / "tiny.csv"
    p.write_text("status,n\ndelivered,3\nshipped,2\ndelivered,1\n")
    return str(p)


class _FakeProvider:
    """Returns a fixed plan, then bad code, then good code on later calls."""

    def __init__(self, good_code: str):
        self._good = good_code
        self.code_calls = 0

    def call_model_with_usage(self, prompt, *, system=None):
        if "plan" in (system or "").lower() or "short plan" in prompt.lower():
            return "Group by status and count.", 5
        # generate_code calls
        self.code_calls += 1
        if self.code_calls == 1:
            return "```python\nresult = df['NOPE'].value_counts().to_dict()\n```", 10
        return f"```python\n{self._good}\n```", 10


def test_retry_corrects_after_error(tiny_csv, monkeypatch):
    good = textwrap.dedent("""
        counts = df['status'].value_counts()
        result = counts.to_dict()
        chart = {"type": "bar", "x": list(counts.index), "y": [int(v) for v in counts.values]}
        table = counts.reset_index()
    """).strip()

    fake = _FakeProvider(good)
    monkeypatch.setattr(nodes, "LLMClient", _make_fake_client_factory(fake))

    from graph.agent import agentic_ai
    from graph import events_bus

    events_bus.open_stream("retry-test")
    state = {
        "run_id": "retry-test",
        "csv_paths": {"df": tiny_csv},
        "question": "How many orders per status?",
        "schema": [{"name": "status", "dtype": "object"}, {"name": "n", "dtype": "int64"}],
        "sample_rows": [{"status": "delivered", "n": 3}],
        "attempts": [],
        "retries": 0,
        "max_retries": 3,
        "tokens": 0,
        "error": None,
    }
    final = agentic_ai.invoke(state, config={"recursion_limit": 50})

    assert final["status"] == "completed"
    # First attempt failed, second succeeded -> 2 attempts in the trail.
    assert len(final["attempts"]) == 2
    assert final["attempts"][0]["ok"] is False
    assert final["attempts"][0]["error"]  # the error is recorded
    assert final["attempts"][1]["ok"] is True
    assert final["result"]["delivered"] == 2


def test_retry_gives_up_after_cap(tiny_csv, monkeypatch):
    class _AlwaysBad:
        def call_model_with_usage(self, prompt, *, system=None):
            if "short plan" in prompt.lower():
                return "plan", 1
            return "```python\nresult = df['MISSING'].sum()\n```", 1

    monkeypatch.setattr(nodes, "LLMClient", _make_fake_client_factory(_AlwaysBad()))

    from graph.agent import agentic_ai
    from graph import events_bus

    events_bus.open_stream("giveup-test")
    state = {
        "run_id": "giveup-test",
        "csv_paths": {"df": tiny_csv},
        "question": "q",
        "schema": [{"name": "status", "dtype": "object"}],
        "sample_rows": [],
        "attempts": [],
        "retries": 0,
        "max_retries": 2,
        "tokens": 0,
        "error": None,
    }
    final = agentic_ai.invoke(state, config={"recursion_limit": 50})
    assert final["status"] == "failed"
    assert "gave up" in final["error"]
    # Initial attempt + retries up to the cap are all recorded.
    assert len(final["attempts"]) >= 2
