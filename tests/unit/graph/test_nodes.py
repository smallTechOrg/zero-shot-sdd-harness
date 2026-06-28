"""Deterministic node tests (no LLM): execute_sql retry signalling, the privacy
guard aggregate cap, and handle_error message composition."""
import json
from pathlib import Path

import pytest

from analysis import ingest_csv
from graph.nodes import execute_sql, handle_error, pick_chart, privacy_guard
from graph.state import AGG_ROW_CAP

_FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"
_SALES = _FIXTURES / "sales.csv"


@pytest.fixture
def duckdb_path(tmp_path):
    path = tmp_path / "t.duckdb"
    ingest_csv(str(_SALES), str(path), table_name="t")
    return str(path)


def test_execute_sql_success_sets_result(duckdb_path):
    state = {
        "sql": "SELECT region, SUM(sales) AS total FROM t GROUP BY region",
        "dataset_path": duckdb_path,
        "table_name": "t",
        "sql_attempts": 0,
    }
    out = execute_sql(state)
    assert out["sql_error"] is None
    assert out["sql_attempts"] == 1
    assert out["phase"] == "post"
    assert out["result"]["columns"] == ["region", "total"]
    assert out["trace"][-1] == {"step": "execute", "ok": True, "latency_ms": out["trace"][-1]["latency_ms"]}


def test_execute_sql_dialect_error_signals_retry(duckdb_path):
    """A SQLite-ism (julianday) raises a DuckDB Catalog Error -> sql_error set,
    sql_attempts incremented, error NOT set (so the retry edge engages)."""
    state = {
        "sql": "SELECT julianday('2024-01-01') AS bad",
        "dataset_path": duckdb_path,
        "table_name": "t",
        "sql_attempts": 0,
    }
    out = execute_sql(state)
    assert out["sql_error"] is not None
    assert "julianday" in out["sql_error"].lower() or "catalog" in out["sql_error"].lower()
    assert out["sql_attempts"] == 1
    assert out.get("error") is None
    assert out["trace"][-1]["step"] == "execute"
    assert out["trace"][-1]["ok"] is False


def test_privacy_guard_caps_aggregate_rows():
    """The guard bounds the result to AGG_ROW_CAP rows before phrasing."""
    big = {"columns": ["k", "v"], "rows": [[i, i] for i in range(AGG_ROW_CAP + 25)]}
    state = {"phase": "post", "result": big}
    out = privacy_guard(state)
    assert len(out["aggregate"]["rows"]) == AGG_ROW_CAP
    assert out["aggregate"]["truncated"] is True
    assert out["aggregate"]["total_rows"] == AGG_ROW_CAP + 25
    # trace notes the truncation
    assert out["trace"][-1]["step"] == "guard"
    assert out["trace"][-1].get("note") == "truncated"


def test_privacy_guard_pre_phase_passthrough():
    out = privacy_guard({"phase": "pre"})
    assert "aggregate" not in out


def test_handle_error_composes_exhausted_sql_message():
    state = {"sql_error": "Catalog Error: julianday", "sql_attempts": 3}
    out = handle_error(state)
    assert out["status"] == "failed"
    assert "3 attempts" in out["error"]
    assert "julianday" in out["error"]


def test_handle_error_uses_explicit_error():
    out = handle_error({"error": "LLM down"})
    assert out["status"] == "failed"
    assert out["error"] == "LLM down"


def test_pick_chart_degrades_to_table_on_bad_aggregate():
    out = pick_chart({"aggregate": {"columns": [], "rows": []}})
    assert out["chart"]["type"] == "table"
