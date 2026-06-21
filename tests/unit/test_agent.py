import os

os.environ["ANALYST_LLM_PROVIDER"] = "stub"

import json

import pytest

from src.integrations.llm import StubLLMClient, get_llm_client


def test_stub_client_returned_in_stub_mode():
    client = get_llm_client()
    assert isinstance(client, StubLLMClient)


def test_stub_returns_table_intent_for_generic_question():
    client = StubLLMClient()
    raw = client.complete("show top 10 rows of sales")
    parsed = json.loads(raw)
    assert parsed["intent"] == "table"
    assert "sql" in parsed


def test_stub_returns_chart_intent_for_plot_question():
    client = StubLLMClient()
    raw = client.complete("plot revenue over product")
    parsed = json.loads(raw)
    assert parsed["intent"] == "chart"
    assert "sql" in parsed


from src.agent.graph import plan_node, respond_node


def test_plan_node_returns_intent_and_sql():
    state = {
        "question": "show top 10 rows of sales",
        "session_id": "test",
        "datasets": ["sales"],
        "plan": "",
        "sql": "",
        "intent": "table",
        "raw_rows": [],
        "columns": [],
        "response": {},
    }
    result = plan_node(state)
    assert result["intent"] in ("table", "chart")
    assert len(result["sql"]) > 0


def test_respond_node_table_format():
    state = {
        "question": "show rows",
        "session_id": "test",
        "datasets": [],
        "plan": "",
        "sql": "",
        "intent": "table",
        "raw_rows": [["widget", 100], ["gadget", 200]],
        "columns": ["product", "revenue"],
        "response": {},
    }
    result = respond_node(state)
    assert result["response"]["type"] == "table"
    assert "| product | revenue |" in result["response"]["markdown"]


def test_respond_node_chart_format():
    state = {
        "question": "plot revenue",
        "session_id": "test",
        "datasets": [],
        "plan": "",
        "sql": "",
        "intent": "chart",
        "raw_rows": [["widget", 100], ["gadget", 200]],
        "columns": ["product", "revenue"],
        "response": {},
    }
    result = respond_node(state)
    assert result["response"]["type"] == "chart"
    assert "plotly_spec" in result["response"]
    assert result["response"]["plotly_spec"]["data"][0]["x"] == ["widget", "gadget"]
