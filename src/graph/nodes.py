"""Query-pipeline nodes: load_schema → generate_sql → execute_sql → format_answer."""
import json
import time
from pathlib import Path

from graph.state import AgentState
from llm.client import LLMClient

_PROMPTS = Path(__file__).parent.parent / "prompts"
_PREVIEW_ROWS = 50


def _load_prompt(name: str) -> str:
    return (_PROMPTS / name).read_text(encoding="utf-8").strip()


def _render_schema(schema: list[dict]) -> str:
    return "\n".join(f"{c['name']}: {c['type']}" for c in schema)


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        # drop opening fence line (``` or ```sql) and trailing fence
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def load_schema(state: AgentState) -> AgentState:
    try:
        from db.session import create_db_session
        from db.models import Dataset

        with create_db_session() as session:
            ds = session.get(Dataset, state["dataset_id"])
            if ds is None:
                return {**state, "error": f"Dataset {state['dataset_id']} not found."}
            schema = json.loads(ds.schema_json)
            table_name = ds.duckdb_table
        return {**state, "schema": schema, "table_name": table_name}
    except Exception as exc:
        return {**state, "error": f"Failed to load dataset schema: {exc}"}


def generate_sql(state: AgentState) -> AgentState:
    try:
        system = _load_prompt("sql_generate.md")
        prompt = (
            f"Table: {state['table_name']}\n\n"
            f"Schema (column: type):\n{_render_schema(state['schema'])}\n\n"
            f"Question: {state['question']}\n\nSQL:"
        )
        raw = LLMClient().call_model(prompt, system=system)
        sql = _strip_fences(raw)
        if not sql:
            return {**state, "error": "The model returned no SQL for this question."}
        return {**state, "sql": sql}
    except Exception as exc:
        return {**state, "error": f"SQL generation failed: {exc}"}


def execute_sql(state: AgentState) -> AgentState:
    from analytics.duckdb_store import DuckDBStore
    from db.session import create_db_session
    from db.models import AuditLog

    sql = state.get("sql", "")
    started = time.perf_counter()
    columns: list[str] = []
    rows: list[list] = []
    error: str | None = None
    try:
        columns, rows = DuckDBStore().execute_select(sql)
    except Exception as exc:
        error = f"SQL execution failed: {exc}"

    duration_ms = int((time.perf_counter() - started) * 1000)
    row_count = len(rows)

    # Audit on success AND failure.
    try:
        with create_db_session() as session:
            session.add(
                AuditLog(
                    session_id=state.get("session_id"),
                    dataset_id=state.get("dataset_id"),
                    operation="query",
                    sql_text=sql,
                    status="error" if error else "success",
                    row_count=None if error else row_count,
                    error_message=error,
                    duration_ms=duration_ms,
                )
            )
    except Exception:
        # Audit failure must never crash the query path.
        pass

    if error:
        return {**state, "error": error}
    return {**state, "columns": columns, "rows": rows, "row_count": row_count}


def format_answer(state: AgentState) -> AgentState:
    try:
        system = _load_prompt("format_answer.md")
        columns = state.get("columns", [])
        rows = state.get("rows", [])
        preview = rows[:_PREVIEW_ROWS]
        preview_json = json.dumps(
            {"columns": columns, "rows": preview}, default=str
        )
        prompt = (
            f"Question: {state['question']}\n\n"
            f"Total rows in result: {state.get('row_count', len(rows))}\n"
            f"Result preview (first {len(preview)} rows):\n{preview_json}\n\n"
            f"Answer:"
        )
        answer = LLMClient().call_model(prompt, system=system)
        return {**state, "answer": (answer or "").strip()}
    except Exception as exc:
        return {**state, "error": f"Answer formatting failed: {exc}"}


def handle_error(state: AgentState) -> AgentState:
    return {**state, "status": "failed"}


def finalize(state: AgentState) -> AgentState:
    return {**state, "status": "completed"}
