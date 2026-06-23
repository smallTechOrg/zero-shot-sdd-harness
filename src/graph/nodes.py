"""
Analyst graph nodes for the SQLite-backed data analyst agent.

Each node receives an AnalystState dict and returns a (possibly updated) AnalystState dict.
All imports use bare module names (pythonpath = ["src"] in pyproject.toml).
"""
import time
import structlog
from pathlib import Path

from graph.state import AnalystState

log = structlog.get_logger()

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "query_planner.md"
_MAX_RESULT_ROWS = 1000


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def _write_audit(
    *,
    session_id: str,
    dataset_table: str,
    question: str,
    sql: str | None,
    row_count: int | None,
    duration_ms: int | None,
    error: str | None,
) -> str:
    """Write an AuditLogRow to SQLite. Non-fatal — returns audit id or '' on failure."""
    try:
        from db.session import create_db_session
        from db.models import AuditLogRow

        with create_db_session() as session:
            row = AuditLogRow(
                session_id=session_id,
                dataset_table=dataset_table,
                question=question,
                sql_generated=sql,
                row_count=row_count,
                duration_ms=duration_ms,
                error=error,
            )
            session.add(row)
            session.flush()
            return row.id
    except Exception as exc:
        log.warning("audit.write_failed", error=str(exc))
        return ""


# ---------------------------------------------------------------------------
# query_planner
# ---------------------------------------------------------------------------

def query_planner(state: AnalystState) -> AnalystState:
    """
    Reads the dataset schema, builds the system prompt with schema context,
    calls Gemini via structured tool-use to generate SQL, and validates the result.
    """
    try:
        from sqlalchemy import text as sa_text
        from db.session import _get_engine

        dataset_table = state["dataset_table"]
        question = state["question"]

        # Fetch schema via PRAGMA
        engine = _get_engine()
        with engine.connect() as conn:
            result = conn.execute(sa_text(f'PRAGMA table_info("{dataset_table}")'))
            columns_info = result.fetchall()

        if not columns_info:
            return {**state, "error": f"Table '{dataset_table}' not found or has no columns"}

        # Build schema context string
        col_descriptions = ", ".join(
            f"{row[1]} ({row[2]})" for row in columns_info
        )
        schema_context = f"Table: {dataset_table}\nColumns: {col_descriptions}"

        # Load prompt and inject schema
        prompt_template = _load_prompt()
        system_prompt = prompt_template.replace("{SCHEMA_CONTEXT}", schema_context)

        # Call Gemini
        from llm.providers.gemini import get_gemini_provider
        provider = get_gemini_provider()
        sql, explanation = provider.plan_sql(system_prompt, question)

        # Validate it is a read-only statement (SELECT or CTE starting with WITH)
        normalised = sql.strip().upper()
        if not (normalised.startswith("SELECT") or normalised.startswith("WITH")):
            return {
                **state,
                "error": f"LLM generated a non-read statement: {sql[:80]}",
            }

        return {
            **state,
            "schema_context": schema_context,
            "sql": sql,
            "sql_explanation": explanation,
        }

    except Exception as exc:
        log.error("query_planner.failed", error=str(exc))
        return {**state, "error": str(exc)}


# ---------------------------------------------------------------------------
# sql_executor
# ---------------------------------------------------------------------------

def sql_executor(state: AnalystState) -> AnalystState:
    """
    Executes the generated SQL against SQLite using raw text() execution.
    Records wall-clock duration and caps rows at 1000.
    """
    try:
        from sqlalchemy import text as sa_text, exc as sa_exc
        from db.session import _get_engine

        sql = state["sql"]
        start = time.monotonic()
        engine = _get_engine()

        with engine.connect() as conn:
            result = conn.execute(sa_text(sql))
            col_names = list(result.keys())
            all_rows = result.fetchall()

        duration_ms = int((time.monotonic() - start) * 1000)
        row_count = len(all_rows)
        rows = [dict(zip(col_names, row)) for row in all_rows[:_MAX_RESULT_ROWS]]

        return {
            **state,
            "rows": rows,
            "row_count": row_count,
            "duration_ms": duration_ms,
        }

    except Exception as exc:
        # Capture SQLAlchemy errors and general errors
        log.error("sql_executor.failed", error=str(exc))
        return {**state, "error": f"SQL execution failed: {exc}"}


# ---------------------------------------------------------------------------
# response_formatter
# ---------------------------------------------------------------------------

def _format_answer(
    sql_explanation: str,
    rows: list[dict],
    row_count: int,
) -> str:
    """Build a plain-text explanation — the frontend renders the table separately."""
    parts: list[str] = [sql_explanation]

    if not rows:
        parts.append("No results found for that query.")
    else:
        shown = len(rows)
        if row_count > shown:
            parts.append(f"Showing {shown} of {row_count} rows.")

    return "\n\n".join(p for p in parts if p)


def response_formatter(state: AnalystState) -> AnalystState:
    """
    Formats the query result into a human-readable markdown answer
    and passes through the table rows.
    """
    try:
        sql_explanation = state.get("sql_explanation", "")
        rows = state.get("rows") or []
        row_count = state.get("row_count") or 0

        answer = _format_answer(sql_explanation, rows, row_count)

        return {
            **state,
            "answer": answer,
            "table": rows,
        }
    except Exception as exc:
        log.error("response_formatter.failed", error=str(exc))
        # Non-fatal fallback
        return {
            **state,
            "answer": "Query completed but formatting failed.",
            "table": state.get("rows") or [],
        }


# ---------------------------------------------------------------------------
# audit_logger
# ---------------------------------------------------------------------------

def audit_logger(state: AnalystState) -> AnalystState:
    """Writes the successful query to the audit log."""
    audit_id = _write_audit(
        session_id=state.get("session_id", ""),
        dataset_table=state.get("dataset_table", ""),
        question=state.get("question", ""),
        sql=state.get("sql"),
        row_count=state.get("row_count"),
        duration_ms=state.get("duration_ms"),
        error=None,
    )
    return {**state, "audit_id": audit_id}


# ---------------------------------------------------------------------------
# handle_error
# ---------------------------------------------------------------------------

def handle_error(state: AnalystState) -> AnalystState:
    """Logs the error and writes an audit entry (best-effort)."""
    error_text = state.get("error") or "Unknown error"
    log.error(
        "analyst.handle_error",
        session_id=state.get("session_id"),
        dataset_table=state.get("dataset_table"),
        error=error_text,
    )
    # Best-effort audit write
    _write_audit(
        session_id=state.get("session_id", ""),
        dataset_table=state.get("dataset_table", ""),
        question=state.get("question", ""),
        sql=state.get("sql"),
        row_count=None,
        duration_ms=state.get("duration_ms"),
        error=error_text,
    )
    return state


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------

def finalize(state: AnalystState) -> AnalystState:
    """No-op pass-through."""
    return state
