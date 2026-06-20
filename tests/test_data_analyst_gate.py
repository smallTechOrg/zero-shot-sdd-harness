"""Data Analyst gate tests — P1 capability: NL query over CSV dataset."""
import os
import pytest
import pandas as pd
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.guardrails import safe_eval
from agent.graph import build_graph
from agent.runner import DOMAIN_PROMPT
from agent.sessions import current_session_id, load_resource, release_session


CSV_DATA = """month,revenue,units_sold,category
January,45000,450,Electronics
February,38000,380,Electronics
March,52000,520,Software
April,61000,610,Software
May,48000,480,Electronics
June,73000,730,Software
July,65000,650,Electronics
August,55000,550,Software
September,69000,690,Software
October,82000,820,Electronics
November,91000,910,Electronics
December,88000,880,Electronics
"""


# -----------------------------------------------------------
# Guardrail unit test (no API key needed)
# -----------------------------------------------------------

def test_rejects_unsafe_code():
    """safe_eval blocks filesystem and shell operations in pandas code."""
    with pytest.raises(ValueError):
        safe_eval("open('/etc/passwd')", {})
    with pytest.raises(ValueError):
        safe_eval("__import__('os').system('id')", {})
    df = pd.DataFrame({"revenue": [45000, 38000, 52000]})
    import numpy as np
    assert safe_eval("df['revenue'].sum()", {"df": df, "pd": pd, "np": np}) == 135000


# -----------------------------------------------------------
# Mechanical loop test (no API key needed)
# -----------------------------------------------------------

async def test_fake_model_loop_analyst():
    """Graph loop runs: inspect_data → execute_pandas → finish, produces a grounded answer."""
    sid = "analyst-loop-sess"
    load_resource(sid, CSV_DATA)

    scripted = [
        AIMessage(content="", tool_calls=[{"name": "inspect_data", "args": {}, "id": "a"}]),
        AIMessage(content="", tool_calls=[{"name": "execute_pandas", "args": {"code": "df['revenue'].sum()"}, "id": "b"}]),
        AIMessage(content="", tool_calls=[{"name": "finish", "args": {"answer": "Total revenue is 767,000."}, "id": "c"}]),
    ]

    class FakeModel:
        def __init__(self, s):
            self.s = list(s); self.i = 0
        def bind_tools(self, tools): return self
        async def ainvoke(self, msgs):
            m = self.s[min(self.i, len(self.s) - 1)]; self.i += 1; return m

    graph = build_graph(FakeModel(scripted))
    state = {
        "messages": [SystemMessage(content=DOMAIN_PROMPT), HumanMessage(content="What is the total revenue?")],
        "iterations": 0, "answer": None, "chart": None, "run_id": "analyst-loop-1",
    }
    token = current_session_id.set(sid)
    try:
        result = await graph.ainvoke(state, config={"recursion_limit": 50})
    finally:
        current_session_id.reset(token)
        release_session(sid)

    assert result["iterations"] >= 3
    assert result["answer"] and "767" in result["answer"]


# -----------------------------------------------------------
# Real LLM tests (require funded key — skipped otherwise)
# -----------------------------------------------------------

@pytest.mark.skipif(not os.getenv("APP_LLM_API_KEY"), reason="real run + LLM judge needs a funded key")
async def test_csv_aggregate():
    """Upload CSV, ask for total revenue → agent executes pandas and returns 767,000."""
    from agent.runner import run_agent
    from agent.evals import stable_outcome_eval
    from agent.gate_eval import CRITERION, EVALUATION_STEPS

    sid = "analyst-gate-1"
    load_resource(sid, CSV_DATA)
    GOAL = "What is the total revenue across all months?"
    state = await run_agent(GOAL, run_id="analyst-agg-1", session_id=sid)
    assert state["status"] == "completed"
    assert state["answer"] and "767" in state["answer"], f"expected 767,000 in answer: {state['answer']}"

    ok_o, mean, detail = await stable_outcome_eval(
        goal=GOAL, answer=state["answer"],
        criterion=CRITERION, evaluation_steps=EVALUATION_STEPS,
    )
    release_session(sid)
    assert ok_o, f"OUTCOME failed: judge mean {mean} {detail}"


@pytest.mark.skipif(not os.getenv("APP_LLM_API_KEY"), reason="real run needs a funded key")
async def test_followup_retains_dataset():
    """A follow-up on the same session uses the retained dataset — no re-upload needed."""
    from agent.runner import run_agent

    sid = "analyst-retain-1"
    load_resource(sid, CSV_DATA)

    s1 = await run_agent("What is the total revenue?", run_id="retain-1", session_id=sid)
    assert s1["status"] == "completed"

    s2 = await run_agent("Which month had the highest revenue?", run_id="retain-2", session_id=sid)
    release_session(sid)
    assert s2["status"] == "completed"
    ans = (s2["answer"] or "").lower()
    assert "november" in ans, f"expected November in follow-up answer, got: {s2['answer']}"
