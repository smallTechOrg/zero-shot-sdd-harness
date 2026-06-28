"""Sandbox unit tests — no LLM key required."""
import textwrap

import pytest

from analyst.sandbox import run_code, _build_chart_spec


@pytest.fixture
def tiny_csv(tmp_path):
    p = tmp_path / "tiny.csv"
    p.write_text("status,n\ndelivered,3\nshipped,2\ndelivered,1\n")
    return str(p)


def test_run_code_happy_path(tiny_csv):
    code = textwrap.dedent("""
        counts = df['status'].value_counts()
        result = counts.to_dict()
        chart = {"type": "bar", "x": list(counts.index), "y": [int(v) for v in counts.values]}
        table = counts.reset_index()
    """)
    res = run_code({"df": tiny_csv}, code, timeout=30)
    assert res.ok, res.error
    assert res.result["delivered"] == 2
    assert res.result["shipped"] == 1
    assert res.chart_spec is not None
    assert res.chart_spec["data"][0]["type"] == "bar"
    assert isinstance(res.table, list) and len(res.table) == 2


def test_run_code_missing_result_is_error(tiny_csv):
    res = run_code({"df": tiny_csv}, "x = df.shape", timeout=30)
    assert not res.ok
    assert "result" in res.error.lower()


def test_run_code_exception_returns_traceback(tiny_csv):
    res = run_code({"df": tiny_csv}, "result = df['nope'].sum()", timeout=30)
    assert not res.ok
    assert "KeyError" in res.error or "nope" in res.error


def test_run_code_bad_path():
    res = run_code({"df": "/does/not/exist.csv"}, "result = 1", timeout=10)
    assert not res.ok
    assert "exist" in res.error.lower()


def test_run_code_timeout(tiny_csv):
    res = run_code({"df": tiny_csv}, "while True:\n    pass", timeout=2)
    assert not res.ok
    assert "timed out" in res.error.lower()


def test_build_chart_spec_pie():
    spec = _build_chart_spec({"type": "pie", "x": ["a", "b"], "y": [1, 2]})
    assert spec["data"][0]["type"] == "pie"


def test_build_chart_spec_none():
    assert _build_chart_spec(None) is None
    assert _build_chart_spec({}) is None
