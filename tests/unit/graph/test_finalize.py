"""Unit tests for the finalize answer-finalization layer:

  - deterministic table synthesis (scalar / dict / Series / list shapes), and
  - the conservative "unanswerable-from-this-dataset" detector + message.

These run without a real LLM key — they exercise pure helpers in graph.nodes.
"""
import numpy as np
import pandas as pd

from graph.nodes import (
    _is_unanswerable_result,
    _unanswerable_message,
    finalize,
    synthesize_table,
)

_SCHEMA = [
    {"name": "order_id", "dtype": "object"},
    {"name": "order_status", "dtype": "object"},
    {"name": "order_purchase_timestamp", "dtype": "object"},
]


# --------------------------------------------------------------------------- #
# Table synthesis
# --------------------------------------------------------------------------- #
def test_synthesize_scalar_int():
    state = {"question": "How many orders?", "result": 99441}
    table = synthesize_table(state)
    assert isinstance(table, list) and len(table) == 1
    row = table[0]
    assert list(row.values())[0] == 99441


def test_synthesize_scalar_float_numpy():
    state = {"question": "Average price?", "result": np.float64(12.5)}
    table = synthesize_table(state)
    assert table and list(table[0].values())[0] == 12.5
    # Must be JSON-safe: a plain python float, not a numpy scalar.
    assert isinstance(list(table[0].values())[0], float)


def test_synthesize_scalar_string_percentage():
    state = {"question": "What percent delivered?", "result": "97.0%"}
    table = synthesize_table(state)
    assert table and list(table[0].values())[0] == "97.0%"


def test_synthesize_dict():
    state = {"question": "q", "result": {"delivered": 96478, "shipped": 1107}}
    table = synthesize_table(state)
    assert {"key": "delivered", "value": 96478} in table
    assert {"key": "shipped", "value": 1107} in table


def test_synthesize_series():
    s = pd.Series({"delivered": 3, "shipped": 2})
    state = {"question": "q", "result": s}
    # A Series result is coerced to a dict by the sandbox in practice; here we
    # pass the raw Series to prove the parent-side coercion also handles it.
    table = synthesize_table(state)
    assert {"key": "delivered", "value": 3} in table


def test_synthesize_list_of_records_passthrough():
    recs = [{"order_status": "delivered", "count": 96478},
            {"order_status": "shipped", "count": 1107}]
    state = {"question": "q", "result": recs}
    table = synthesize_table(state)
    assert table == recs


def test_synthesize_none_is_none():
    assert synthesize_table({"question": "q", "result": None}) is None


def test_synthesize_nan_is_nulled():
    state = {"question": "q", "result": float("nan")}
    table = synthesize_table(state)
    assert table and list(table[0].values())[0] is None


# --------------------------------------------------------------------------- #
# Unanswerable detector
# --------------------------------------------------------------------------- #
def test_detector_error_prefix():
    assert _is_unanswerable_result("Error: column 'freight_value' not available in this dataset")


def test_detector_phrase_unknown_column():
    assert _is_unanswerable_result("There is no such column freight_value here")


def test_detector_negative_legit_answer_mentioning_column():
    # A legitimate textual answer that merely mentions the word "column" must
    # still succeed (NOT be flagged as unanswerable).
    assert not _is_unanswerable_result(
        "The order_status column has 8 distinct values; delivered is most common."
    )


def test_detector_negative_scalar():
    assert not _is_unanswerable_result(99441)
    assert not _is_unanswerable_result(12.5)
    assert not _is_unanswerable_result({"delivered": 3})


def test_unanswerable_message_lists_available_columns():
    msg = _unanswerable_message({"schema": _SCHEMA})
    assert "can't be answered" in msg
    assert "order_status" in msg
    assert "order_id" in msg


# --------------------------------------------------------------------------- #
# finalize integration of both fixes (pure, no graph)
# --------------------------------------------------------------------------- #
def test_finalize_synthesizes_table_on_success_when_missing():
    state = {
        "run_id": "t",
        "question": "How many orders?",
        "result": 99441,
        "table": None,
        "schema": _SCHEMA,
    }
    out = finalize(state)
    assert out["status"] == "completed"
    assert out["table"], "finalize must carry a synthesized table on success"
    assert list(out["table"][0].values())[0] == 99441


def test_finalize_keeps_existing_table():
    existing = [{"order_status": "delivered", "count": 96478}]
    state = {"run_id": "t", "question": "q", "result": {"delivered": 96478},
             "table": existing, "schema": _SCHEMA}
    out = finalize(state)
    assert out["table"] == existing


def test_finalize_routes_unanswerable_to_failure():
    state = {
        "run_id": "t",
        "question": "What is the average freight_value?",
        "result": "Error: column 'freight_value' not available in this dataset",
        "table": None,
        "schema": _SCHEMA,
    }
    out = finalize(state)
    assert out["status"] == "failed"
    assert out["answer"] is None
    assert "order_status" in out["error"]
    assert "can't be answered" in out["error"]
