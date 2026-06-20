"""Mechanical + guardrail tests (no API key). Old grounded-answer LLM tests are skipped."""
import pytest
import pandas as pd
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.guardrails import safe_eval
from agent.graph import build_graph
from agent.runner import DOMAIN_PROMPT
from agent.sessions import current_session_id, load_resource, release_session


class FakeModel:
    def __init__(self, scripted):
        self.s = list(scripted)
        self.i = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, msgs):
        m = self.s[min(self.i, len(self.s) - 1)]
        self.i += 1
        return m


# -----------------------------------------------------------
# Mechanical loop tests (no API key needed)
# -----------------------------------------------------------

async def test_fake_model_loop():
    """Graph loop runs with data analyst tools: inspect_data → execute_pandas → finish."""
    sid = "test-loop-sess"
    load_resource(sid, "month,revenue\nJan,45000\nFeb,38000\nMar,52000\n")

    scripted = [
        AIMessage(content="", tool_calls=[{"name": "inspect_data", "args": {}, "id": "a"}]),
        AIMessage(content="", tool_calls=[{"name": "execute_pandas", "args": {"code": "df['revenue'].sum()"}, "id": "b"}]),
        AIMessage(content="", tool_calls=[{"name": "finish", "args": {"answer": "Total revenue is 135,000."}, "id": "c"}]),
    ]

    graph = build_graph(FakeModel(scripted))
    state = {
        "messages": [SystemMessage(content=DOMAIN_PROMPT), HumanMessage(content="What is the total revenue?")],
        "iterations": 0, "answer": None, "chart": None, "run_id": "test-loop-1",
    }
    token = current_session_id.set(sid)
    try:
        result = await graph.ainvoke(state, config={"recursion_limit": 50})
    finally:
        current_session_id.reset(token)
        release_session(sid)

    assert result["iterations"] >= 3
    assert result["answer"] is not None
    assert result["answer"] != "(no answer produced)"


async def test_force_finalize():
    """When the model loops without calling finish, force_finalize terminates it with an answer."""
    looping = AIMessage(content="thinking...", tool_calls=[])

    class LoopingModel:
        def bind_tools(self, tools): return self
        async def ainvoke(self, msgs): return looping

    graph = build_graph(LoopingModel())
    state = {
        "messages": [SystemMessage(content=DOMAIN_PROMPT), HumanMessage(content="test")],
        "iterations": 0, "answer": None, "chart": None, "run_id": "test-runaway",
    }
    result = await graph.ainvoke(state, config={"recursion_limit": 50})
    assert result["answer"] is not None, "force_finalize must produce an answer, never None"


# -----------------------------------------------------------
# Guardrail unit tests (no API key) — AST-safe-eval utility
# -----------------------------------------------------------

def test_refuses_filesystem_escape():
    with pytest.raises(ValueError):
        safe_eval("open('/etc/passwd')", {})
    with pytest.raises(ValueError):
        safe_eval("__import__('os').system('id')", {})


def test_refuses_destructive():
    with pytest.raises(ValueError):
        safe_eval("().__class__.__mro__", {})
    with pytest.raises(ValueError):
        safe_eval("eval('1+1')", {})


def test_safe_eval_allows_pandas():
    df = pd.DataFrame({"age": [30, 25, 35]})
    assert abs(safe_eval("df['age'].mean()", {"df": df, "pd": pd}) - 30.0) < 0.01


# -----------------------------------------------------------
# Old grounded-answer LLM tests — skipped (capability replaced by data-analysis)
# -----------------------------------------------------------

@pytest.mark.skip(reason="grounded-answer capability replaced by data-analysis (P1 switch)")
async def test_demo_gate():
    pass


@pytest.mark.skip(reason="grounded-answer capability replaced by data-analysis (P1 switch)")
async def test_followup_retains_document():
    pass
