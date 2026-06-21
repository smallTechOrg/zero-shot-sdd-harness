"""FR-001 NL querying criteria — stub agent loop gate (no API key required).

Uses a ContextAwareFakeModel that reads real DuckDB query output to construct a grounded answer
with a Markdown table and a Plotly chart spec.

Gate command: uv run --extra dev pytest tests/test_query_fr.py -v
"""
import csv as csv_mod
import json
import os
import tempfile
import time

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, ToolMessage

from src.runner import run_agent, DOMAIN_PROMPT


# ---------------------------------------------------------------------------
# Helpers (same pattern as test_capabilities.py)
# ---------------------------------------------------------------------------

def _tc(name: str, args: dict, tid: str):
    return {"id": tid, "name": name, "args": args, "type": "tool_call"}


def _tool_msgs(messages) -> list[ToolMessage]:
    return [m for m in messages if isinstance(m, ToolMessage)]


def _last_tool_json(messages):
    tms = _tool_msgs(messages)
    if not tms:
        return {}
    try:
        return json.loads(tms[-1].content)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def seeded_fr_dataset():
    """Real CSV → DuckDB with numeric + categorical columns for FR gate tests."""
    from src.domain import Dataset, DataTable
    from src.db import get_sessionmaker
    from src import duck

    ds = Dataset(name="fr_gate_sales")
    async with get_sessionmaker()() as s:
        s.add(ds)
        await s.commit()
        ds_id = ds.id

    rows = [
        ["category", "revenue", "region"],
        ["Electronics", 3000, "West"],
        ["Furniture", 1050, "East"],
        ["Office", 450, "West"],
        ["Books", 200, "East"],
        ["Clothing", 150, "North"],
    ]
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="") as f:
        csv_mod.writer(f).writerows(rows)
        tmp = f.name

    import asyncio
    try:
        meta = await asyncio.to_thread(duck.ingest_file, ds_id, "sales.csv", tmp, "sales.csv")
    finally:
        os.unlink(tmp)

    async with get_sessionmaker()() as s:
        s.add(DataTable(
            dataset_id=ds_id,
            table_name=meta["table_name"],
            filename=meta["filename"],
            n_rows=meta["n_rows"],
            n_cols=meta["n_cols"],
            columns=meta["columns"],
        ))
        await s.commit()

    return ds_id, meta["table_name"]


# ---------------------------------------------------------------------------
# FR-001 criterion: NL query returns Markdown table and Plotly chart spec
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nl_query_returns_markdown_table_and_chart_spec(seeded_fr_dataset):
    """WHEN user sends NL question, system SHALL return result set with Markdown table and Plotly chart spec.

    The FakeModel:
      Step 1: get_dataset_schema — confirm columns exist
      Step 2: execute_sql       — SELECT category + SUM(revenue)
      Step 3: generate_chart_spec — produce Plotly bar spec
      Step 4: finish(answer=<Markdown table>, chart_spec=<Plotly JSON>)
    """
    ds_id, table = seeded_fr_dataset

    class _FRModel:
        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            n = len(_tool_msgs(messages))
            if n == 0:
                return AIMessage(content="", tool_calls=[
                    _tc("get_dataset_schema", {"dataset_id": ds_id}, "t1")])
            if n == 1:
                return AIMessage(content="", tool_calls=[
                    _tc("execute_sql", {
                        "dataset_id": ds_id,
                        "sql": (
                            f"SELECT category, SUM(revenue) AS total_revenue "
                            f"FROM {table} GROUP BY category ORDER BY total_revenue DESC"
                        ),
                    }, "t2")])
            if n == 2:
                return AIMessage(content="", tool_calls=[
                    _tc("generate_chart_spec", {
                        "query_results": _tool_msgs(messages)[-1].content,
                        "chart_type": "bar",
                        "x_col": "category",
                        "y_col": "total_revenue",
                        "title": "Revenue by Category",
                    }, "t3")])
            # Step 4: build Markdown table from actual SQL rows + attach chart_spec
            sql_data = {}
            # scan backwards for the execute_sql tool output (2nd-to-last tool message)
            tms = _tool_msgs(messages)
            for tm in reversed(tms[:-1]):
                try:
                    sql_data = json.loads(tm.content)
                    break
                except Exception:
                    continue

            rows = sql_data.get("rows", [])
            cols = sql_data.get("columns", ["category", "total_revenue"])

            # Build Markdown table from real query results
            header = "| " + " | ".join(cols) + " |"
            sep = "| " + " | ".join("---" for _ in cols) + " |"
            body_lines = ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
            md_table = "\n".join([header, sep] + body_lines)

            chart_spec_str = _tool_msgs(messages)[-1].content  # last tool is generate_chart_spec output

            return AIMessage(content="", tool_calls=[
                _tc("finish", {
                    "answer": f"Here is the revenue breakdown by category:\n\n{md_table}",
                    "chart_spec": chart_spec_str,
                }, "t4")])

    result = await run_agent(
        goal="Show me total revenue by category with a bar chart",
        dataset_id=ds_id,
        model=_FRModel(),
    )

    assert result["run_id"], "run_id must be present"
    assert result["thread_id"], "thread_id must be present"
    assert result["status"] == "completed"

    # Markdown table criterion
    assert result["answer"], "answer must not be empty"
    assert "|" in result["answer"], (
        f"answer must contain a Markdown table (| character). Got: {result['answer']!r}")

    # Plotly chart spec criterion
    assert result["chart_spec"] is not None, "chart_spec must be present when chart was requested"
    spec = (
        json.loads(result["chart_spec"])
        if isinstance(result["chart_spec"], str)
        else result["chart_spec"]
    )
    assert "data" in spec, f"Plotly spec must have 'data' key. Got keys: {list(spec.keys())}"
    assert "layout" in spec, f"Plotly spec must have 'layout' key. Got keys: {list(spec.keys())}"
    assert isinstance(spec["data"], list) and len(spec["data"]) > 0, (
        "Plotly spec 'data' must be a non-empty list")


# ---------------------------------------------------------------------------
# FR-001 criterion: result returned within 30 seconds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_within_30_seconds(seeded_fr_dataset):
    """WHEN user sends NL question, result SHALL be returned within 30 seconds."""
    ds_id, table = seeded_fr_dataset

    class _FastModel:
        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            n = len(_tool_msgs(messages))
            if n == 0:
                return AIMessage(content="", tool_calls=[
                    _tc("execute_sql", {
                        "dataset_id": ds_id,
                        "sql": f"SELECT category, revenue FROM {table} ORDER BY revenue DESC LIMIT 3",
                    }, "t1")])
            data = _last_tool_json(messages)
            rows = data.get("rows", [])
            cols = data.get("columns", ["category", "revenue"])
            header = "| " + " | ".join(cols) + " |"
            sep = "| " + " | ".join("---" for _ in cols) + " |"
            body_lines = ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
            md_table = "\n".join([header, sep] + body_lines)
            return AIMessage(content="", tool_calls=[
                _tc("finish", {"answer": f"Top 3 categories:\n\n{md_table}"}, "t2")])

    start = time.time()
    result = await run_agent(
        goal="What are the top 3 categories by revenue?",
        dataset_id=ds_id,
        model=_FastModel(),
    )
    elapsed = time.time() - start

    assert elapsed < 30, f"Run took {elapsed:.2f}s — must complete within 30 seconds"
    assert result["status"] == "completed"
    assert "|" in result["answer"], (
        f"answer must contain a Markdown table. Got: {result['answer']!r}")


# ---------------------------------------------------------------------------
# FR-001 sanity: DOMAIN_PROMPT instructs Markdown table formatting
# ---------------------------------------------------------------------------

def test_domain_prompt_instructs_markdown_table():
    """The DOMAIN_PROMPT must tell the LLM to produce Markdown tables for tabular results."""
    assert "Markdown table" in DOMAIN_PROMPT, (
        "DOMAIN_PROMPT must contain 'Markdown table' instruction so the real LLM formats results correctly")
