"""Offline unit tests for the ReAct graph (slice-2b).

Zero env vars, no network, in-memory SQLite (via the autouse `_isolated_db`
fixture in conftest). The stub LLM provider drives the loop: it branches only on
the injected `<node:plan>` / `<node:finalize>` tags. The combined unit suite is
run by the orchestrator after slice-2a (the stub provider + `client.py` stub
branch) lands; these tests pass once `LLMClient` honors `AGENT_LLM_PROVIDER=stub`.
"""
from __future__ import annotations

import pandas as pd
import pytest

from db.models import DatasetRow
from db.session import create_db_session
from graph import nodes as nodes_module
from graph.edges import after_execute, after_plan, after_setup


@pytest.fixture(autouse=True)
def _force_stub_provider(monkeypatch):
    """Make `LLMClient` use the offline stub provider for every test here."""
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "stub")
    monkeypatch.delenv("AGENT_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_OPENROUTER_API_KEY", raising=False)
    # conftest's _reset_settings_singleton already resets the singleton each test.


def _make_dataset(uploads_dir, filename: str = "sales.csv") -> str:
    """Create a tiny CSV on disk + a `datasets` row; return the dataset id."""
    df = pd.DataFrame(
        {
            "product": ["a", "b", "c", "d"],
            "price": [10.0, 20.0, 30.0, 40.0],
            "qty": [1, 2, 3, 4],
        }
    )
    with create_db_session() as session:
        row = DatasetRow(
            filename=filename,
            file_path="",  # set below once we know the id
            row_count=len(df),
            col_count=len(df.columns),
            columns_json=list(df.columns),
            content_hash="hash-" + filename,
            format="csv",
            origin="uploaded",
        )
        session.add(row)
        session.flush()
        dataset_id = row.id
        csv_path = uploads_dir / f"{dataset_id}.csv"
        df.to_csv(csv_path, index=False)
        row.file_path = str(csv_path)
    return dataset_id


@pytest.fixture
def uploads_dir(tmp_path, monkeypatch):
    """Point the nodes' uploads dir at a tmp dir so setup can load real files."""
    d = tmp_path / "uploads"
    d.mkdir()
    monkeypatch.setattr(nodes_module, "_uploads_dir", lambda: d)
    return d


# --------------------------------------------------------------------------- #
# Compilation
# --------------------------------------------------------------------------- #


def test_graph_compiles():
    from graph.agent import agentic_ai

    assert agentic_ai is not None


def test_runner_signature_importable():
    from graph.runner import run_agent  # noqa: F401

    assert callable(run_agent)


# --------------------------------------------------------------------------- #
# Full run via run_agent (happy path)
# --------------------------------------------------------------------------- #


def test_run_agent_completes_with_answer(uploads_dir):
    from graph.runner import run_agent

    dataset_id = _make_dataset(uploads_dir)
    result = run_agent("What is the average price?", [dataset_id])

    assert result["status"] == "completed"
    assert result["answer"] and isinstance(result["answer"], str)
    assert len(result["answer"]) > 0
    # The stub runs one describe action then a FINAL ANSWER, so at least one step.
    assert len(result["action_history"]) >= 1
    assert result["iteration_count"] >= 1
    assert result["dataset_ids"] == [dataset_id]
    # Tokens are estimated for the stub provider (len//4 heuristic).
    assert result["tokens_input"] > 0
    assert result["tokens_output"] > 0


def test_run_agent_return_dict_keys(uploads_dir):
    """The exact keys slice-2c's /ask route consumes."""
    from graph.runner import run_agent

    dataset_id = _make_dataset(uploads_dir)
    result = run_agent("Describe the data.", [dataset_id])

    expected_keys = {
        "run_id",
        "status",
        "answer",
        "iteration_count",
        "tokens_input",
        "tokens_output",
        "action_history",
        "charts",
        "dataset_ids",
        "is_best_effort",
        "selector_reasoning",
    }
    assert expected_keys.issubset(set(result.keys()))


def test_run_agent_persists_query_run(uploads_dir):
    from db.models import QueryRunRow
    from graph.runner import run_agent

    dataset_id = _make_dataset(uploads_dir)
    result = run_agent("Average price?", [dataset_id])

    with create_db_session() as session:
        row = session.get(QueryRunRow, result["run_id"])
        assert row is not None
        assert row.status == "completed"
        assert row.answer
        assert row.question == "Average price?"
        assert row.dataset_ids_json == [dataset_id]
        assert row.action_history is not None


def test_first_action_executes_describe(uploads_dir):
    """Stub's first <node:plan> reply is `df.describe().to_string()` — it must run
    cleanly against the real loaded DataFrame and be recorded as a non-error step."""
    from graph.runner import run_agent

    dataset_id = _make_dataset(uploads_dir)
    result = run_agent("Summarise.", [dataset_id])

    first = result["action_history"][0]
    assert first["action"] == "df.describe().to_string()"
    assert first["is_error"] is False
    assert "price" in first["result"]  # describe output mentions the numeric columns


def test_run_releases_dataframe_registry(uploads_dir):
    from graph.runner import run_agent

    dataset_id = _make_dataset(uploads_dir)
    result = run_agent("Average price?", [dataset_id])

    # finalize/force_finalize/handle_error all release the run-scoped frame.
    assert result["run_id"] not in nodes_module._dataframes


# --------------------------------------------------------------------------- #
# Error path: missing data file -> handle_error -> failed
# --------------------------------------------------------------------------- #


def test_missing_dataset_file_routes_to_handle_error(uploads_dir):
    from graph.runner import run_agent

    # Insert a datasets row but DO NOT write the CSV -> setup load fails.
    with create_db_session() as session:
        row = DatasetRow(
            filename="ghost.csv",
            file_path="",
            row_count=0,
            col_count=0,
            columns_json=[],
            content_hash="ghost",
            format="csv",
            origin="uploaded",
        )
        session.add(row)
        session.flush()
        dataset_id = row.id

    result = run_agent("anything", [dataset_id])
    assert result["status"] == "failed"
    assert result["answer"] is None


def test_unknown_dataset_id_fails(uploads_dir):
    from graph.runner import run_agent

    result = run_agent("anything", ["does-not-exist"])
    assert result["status"] == "failed"


# --------------------------------------------------------------------------- #
# Edge routers (unit-level, no LLM)
# --------------------------------------------------------------------------- #


def test_after_setup_routes_on_error():
    assert after_setup({"error": "boom"}) == "handle_error"
    assert after_setup({}) == "plan_action"


def test_after_plan_final_answer_routes_to_finalize():
    assert after_plan({"llm_response": "FINAL ANSWER: 42"}) == "finalize"
    assert after_plan({"llm_response": "...some preamble... final answer: x"}) == "finalize"
    assert after_plan({"llm_response": "df['price'].mean()"}) == "execute_action"
    assert after_plan({"error": "boom"}) == "handle_error"


def test_after_execute_max_iter_routes_to_force_finalize():
    state = {"iteration_count": 6, "max_iterations": 6, "action_history": []}
    assert after_execute(state) == "force_finalize"


def test_after_execute_consecutive_errors_routes_to_force_finalize():
    history = [{"is_error": True}, {"is_error": True}, {"is_error": True}]
    state = {"iteration_count": 2, "max_iterations": 6, "action_history": history}
    assert after_execute(state) == "force_finalize"


def test_after_execute_recoverable_error_loops_to_plan():
    history = [{"is_error": False}, {"is_error": True}]
    state = {"iteration_count": 2, "max_iterations": 6, "action_history": history}
    assert after_execute(state) == "plan_action"


def test_after_execute_fatal_error_routes_to_handle_error():
    assert after_execute({"error": "fatal", "action_history": []}) == "handle_error"


# --------------------------------------------------------------------------- #
# force_finalize: best-effort completion on max-iter
# --------------------------------------------------------------------------- #


def test_force_finalize_on_max_iter_completes(uploads_dir):
    """With max_iterations=1 the loop force-finalizes after one action."""
    from graph.runner import run_agent

    dataset_id = _make_dataset(uploads_dir)
    result = run_agent("Average price?", [dataset_id], max_iterations=1)

    assert result["status"] == "completed"
    assert result["answer"]
    assert result["is_best_effort"] is True


# --------------------------------------------------------------------------- #
# Sandbox helpers (no LLM, no DB)
# --------------------------------------------------------------------------- #


def test_sandbox_eval_expression_ok():
    from graph.sandbox import build_namespace, eval_expression

    df = pd.DataFrame({"x": [1, 2, 3]})
    ns = build_namespace([df], ["nums.csv"])
    result_str, charts, is_error, error_str = eval_expression("df['x'].sum()", ns)
    assert is_error is False
    assert error_str is None
    assert "6" in result_str
    assert charts == []


def test_sandbox_eval_expression_error_is_recoverable():
    from graph.sandbox import build_namespace, eval_expression

    df = pd.DataFrame({"x": [1, 2, 3]})
    ns = build_namespace([df])
    result_str, charts, is_error, error_str = eval_expression("df['missing'].sum()", ns)
    assert is_error is True
    assert error_str  # non-empty error string fed back to the model


def test_sandbox_namespace_aliases():
    from graph.sandbox import build_namespace

    df1 = pd.DataFrame({"a": [1]})
    df2 = pd.DataFrame({"b": [2]})
    ns = build_namespace([df1, df2], ["sales.csv", "orders.csv"])
    assert ns["df"] is df1
    assert ns["df1"] is df1
    assert ns["df2"] is df2
    assert ns["sales"] is df1
    assert ns["orders"] is df2
    # Libraries present.
    for lib in ("pd", "np", "px", "go", "plt", "sns", "scipy", "stats", "sklearn", "sm"):
        assert lib in ns
    assert callable(ns["save_dataset"])


def test_sandbox_captures_plotly_chart():
    from graph.sandbox import build_namespace, eval_expression

    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    ns = build_namespace([df])
    result_str, charts, is_error, error_str = eval_expression("px.scatter(df, x='x', y='y')", ns)
    assert is_error is False
    assert len(charts) == 1
    assert charts[0].strip().startswith("{")  # JSON string


def test_save_dataset_stub_returns_string_without_writing():
    from graph.sandbox import save_dataset

    df = pd.DataFrame({"x": [1, 2]})
    msg = save_dataset(df, "derived_thing", "a desc")
    assert isinstance(msg, str)
    assert "derived_thing" in msg
