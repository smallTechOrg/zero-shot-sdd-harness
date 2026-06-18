"""Run validated read-only SQL against a dataset's DuckDB engine."""

from __future__ import annotations

from typing import Any

from datachat.data import engine
from datachat.guardrails.sql_safety import SqlSafetyError, validate_read_only

MAX_RESULT_ROWS = 1000


class QueryError(ValueError):
    """A safety rejection or a DuckDB execution error — recoverable in the ReAct loop."""


def run_sql(dataset_id: str, sql: str) -> dict[str, Any]:
    """Validate + execute a read-only SELECT, returning {columns, rows}.

    Raises QueryError (a value the loop observes) on rejection or execution failure;
    never lets a model-generated query crash the run.
    """
    if not engine.has_connection(dataset_id):
        raise QueryError(
            "Session data is no longer available — please re-upload the dataset's files."
        )

    try:
        safe = validate_read_only(sql)
    except SqlSafetyError as exc:
        raise QueryError(f"Query rejected by read-only safety check: {exc}") from exc

    conn = engine.get_connection(dataset_id)
    try:
        cur = conn.execute(safe)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(MAX_RESULT_ROWS)
    except Exception as exc:
        raise QueryError(f"DuckDB error: {exc}") from exc

    return {"columns": columns, "rows": [list(r) for r in rows]}


def inspect_schema(dataset_id: str) -> dict[str, Any]:
    """List the dataset's tables, their columns/types, for the agent to plan a query."""
    if not engine.has_connection(dataset_id):
        raise QueryError(
            "Session data is no longer available — please re-upload the dataset's files."
        )
    conn = engine.get_connection(dataset_id)
    tables: list[dict[str, Any]] = []
    for (table,) in conn.execute("SHOW TABLES").fetchall():
        cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        tables.append(
            {"table": table, "columns": [{"name": c[1], "type": c[2]} for c in cols]}
        )
    return {"tables": tables}
