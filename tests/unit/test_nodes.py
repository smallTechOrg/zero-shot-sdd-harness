"""Unit tests for graph nodes — no real LLM calls, no real DB (for pure nodes)."""
import json
import os
import tempfile

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_csv(data: dict, tmp_path) -> str:
    """Write a DataFrame to a temp CSV and return its path."""
    df = pd.DataFrame(data)
    path = str(tmp_path / "test.csv")
    df.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# ingest_csv
# ---------------------------------------------------------------------------

def test_ingest_csv_success(tmp_path):
    path = _make_csv({"category": ["A", "B", "C"], "value": [10, 20, 30]}, tmp_path)
    from graph.nodes import ingest_csv

    state = {"dataset_path": path, "dataset_id": "test-id"}
    result = ingest_csv(state)

    assert "error" not in result or result.get("error") is None
    assert "schema_summary" in result
    summary = result["schema_summary"]
    assert "category" in summary
    assert "value" in summary


def test_ingest_csv_missing_file(tmp_path):
    from graph.nodes import ingest_csv

    state = {"dataset_path": str(tmp_path / "nonexistent.csv"), "dataset_id": "x"}
    result = ingest_csv(state)

    assert result.get("error") is not None
    assert "ingest_csv" in result["error"]


# ---------------------------------------------------------------------------
# execute_analysis — groupby
# ---------------------------------------------------------------------------

def test_execute_analysis_groupby(tmp_path):
    path = _make_csv(
        {
            "category": ["A", "A", "B", "B"],
            "value": [10, 20, 30, 40],
        },
        tmp_path,
    )
    from graph.nodes import execute_analysis

    state = {
        "dataset_path": path,
        "analysis_plan": {
            "pandas_ops": [
                {"op": "groupby", "by": "category", "agg": {"value": "mean"}}
            ],
            "chart_type": "bar",
            "chart_columns": {"x": "category", "y": "value"},
        },
    }
    result = execute_analysis(state)

    assert result.get("error") is None
    computed = result.get("computed_data", {})
    rows = computed.get("result", [])
    assert isinstance(rows, list)
    # Should have 2 groups: A and B
    assert len(rows) == 2
    by_cat = {r["category"]: r["value"] for r in rows}
    assert abs(by_cat["A"] - 15.0) < 0.01
    assert abs(by_cat["B"] - 35.0) < 0.01


# ---------------------------------------------------------------------------
# generate_chart — bar (no LLM needed)
# ---------------------------------------------------------------------------

def test_generate_chart_bar(tmp_path):
    from graph.nodes import generate_chart

    state = {
        "computed_data": {
            "result": [
                {"category": "A", "value": 10},
                {"category": "B", "value": 20},
            ]
        },
        "analysis_plan": {
            "chart_type": "bar",
            "chart_columns": {"x": "category", "y": "value"},
        },
        "question": "Test chart",
    }
    result = generate_chart(state)

    assert result.get("error") is None
    chart_json = result.get("chart_json")
    assert chart_json is not None
    parsed = json.loads(chart_json)
    assert "data" in parsed


def test_generate_chart_unknown_type(tmp_path):
    from graph.nodes import generate_chart

    state = {
        "computed_data": {
            "result": [{"x": 1, "y": 2}]
        },
        "analysis_plan": {
            "chart_type": "unknown_type",
            "chart_columns": {"x": "x", "y": "y"},
        },
        "question": "Test",
    }
    result = generate_chart(state)

    # Non-fatal: chart_json is None, no error
    assert result.get("chart_json") is None
    assert result.get("error") is None


# ---------------------------------------------------------------------------
# plan_analysis — mocked LLM
# ---------------------------------------------------------------------------

VALID_PLAN = json.dumps({
    "pandas_ops": [{"op": "groupby", "by": "category", "agg": {"value": "mean"}}],
    "chart_type": "bar",
    "chart_columns": {"x": "category", "y": "value"},
    "reasoning": "Group by category and compute mean value.",
})


def test_plan_analysis_mocked(monkeypatch):
    from graph.nodes import plan_analysis

    monkeypatch.setattr(
        "llm.client.LLMClient.call_model",
        lambda self, prompt, **kwargs: VALID_PLAN,
    )

    state = {
        "schema_summary": "category: object\nvalue: int64",
        "question": "What is the average value per category?",
    }
    result = plan_analysis(state)

    assert result.get("error") is None
    plan = result.get("analysis_plan")
    assert plan is not None
    assert "pandas_ops" in plan
    assert plan["chart_type"] == "bar"


def test_plan_analysis_retry_on_bad_json(monkeypatch):
    """First call returns non-JSON, second call returns valid JSON — retry succeeds."""
    call_count = {"n": 0}

    def _mock_call(self, prompt, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "This is not JSON at all."
        return VALID_PLAN

    monkeypatch.setattr("llm.client.LLMClient.call_model", _mock_call)

    from graph.nodes import plan_analysis

    state = {
        "schema_summary": "col: int",
        "question": "What is the sum?",
    }
    result = plan_analysis(state)

    assert result.get("error") is None
    assert result.get("analysis_plan") is not None
    assert call_count["n"] == 2


def test_plan_analysis_fails_after_retry(monkeypatch):
    """Both calls return non-JSON — error is set."""
    monkeypatch.setattr(
        "llm.client.LLMClient.call_model",
        lambda self, prompt, **kwargs: "Not JSON either",
    )

    from graph.nodes import plan_analysis

    state = {
        "schema_summary": "col: int",
        "question": "What?",
    }
    result = plan_analysis(state)

    assert result.get("error") is not None
    assert "plan_analysis" in result["error"]
    assert "invalid JSON" in result["error"]
