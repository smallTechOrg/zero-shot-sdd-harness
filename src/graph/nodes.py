import json
import re
from pathlib import Path

from graph.state import AgentState
from llm.client import LLMClient

from data.sql_guard import SqlNotAllowed, assert_read_only
from data.executor import run_read_only
from data.audit import log_operation

_PROMPTS = Path(__file__).parent.parent / "prompts"
_TRANSFORM_PATH = _PROMPTS / "transform.md"
_ANALYST_PATH = _PROMPTS / "analyst.md"
_FORMAT_PATH = _PROMPTS / "format.md"

# Cap rows sent to the format LLM call to stay token-economical.
_FORMAT_ROW_PREVIEW = 30


def _load_prompt() -> str:
    return _TRANSFORM_PATH.read_text(encoding="utf-8").strip()


# --- Skeleton transform slot (kept for /runs and existing tests) ---


def transform_text(state: AgentState) -> AgentState:
    try:
        prompt_template = _load_prompt()
        result = LLMClient().call_model(
            f"{prompt_template}\n\nInput: {state['input_text']}"
        )
        return {**state, "output_text": result}
    except Exception as exc:
        return {**state, "error": str(exc)}


# --- Analyst pipeline ---


def _strip_sql_fences(raw: str) -> str:
    text = raw.strip()
    # Strip a leading ```sql / ``` fence and trailing fence if present.
    fence = re.match(r"^```[a-zA-Z]*\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    return text.strip()


def _build_generate_user_message(state: AgentState) -> str:
    schema = state.get("schema") or []
    sample = state.get("sample") or {"columns": [], "rows": []}
    history = state.get("history") or []
    table = state.get("table_name", "")

    schema_lines = "\n".join(f"  - {c['name']} ({c['type']})" for c in schema)

    parts = [
        f"Table name: {table}",
        f"Schema:\n{schema_lines}",
        "Sample rows (JSON):",
        json.dumps(sample, default=str),
    ]
    if history:
        ctx = "\n".join(
            f"  Q: {h.get('question', '')}\n  SQL: {h.get('sql_text', '')}"
            for h in history
        )
        parts.append(f"Recent prior turns (for context):\n{ctx}")
    parts.append(f"Question: {state.get('question', '')}")
    return "\n\n".join(parts)


def generate_sql(state: AgentState) -> AgentState:
    try:
        system = _ANALYST_PATH.read_text(encoding="utf-8").strip()
        user = _build_generate_user_message(state)
        raw = LLMClient().call_model(user, system=system)
        sql = _strip_sql_fences(raw)
        if not sql:
            return {**state, "error": "Model returned an empty SQL query."}
        return {**state, "sql_text": sql}
    except Exception as exc:
        return {**state, "error": f"SQL generation failed: {exc}"}


def validate_sql(state: AgentState) -> AgentState:
    sql = state.get("sql_text") or ""
    try:
        cleaned = assert_read_only(sql)
        return {**state, "sql_text": cleaned}
    except SqlNotAllowed as exc:
        log_operation(
            session_id=state.get("session_id"),
            operation="blocked",
            question=state.get("question"),
            sql_text=sql,
            rows_returned=None,
            success=False,
            error_message=str(exc),
        )
        return {**state, "error": f"Query rejected by read-only guard: {exc}"}
    except Exception as exc:
        return {**state, "error": f"SQL validation failed: {exc}"}


def execute_sql(state: AgentState) -> AgentState:
    sql = state.get("sql_text") or ""
    try:
        result = run_read_only(sql)
        log_operation(
            session_id=state.get("session_id"),
            operation="query",
            question=state.get("question"),
            sql_text=sql,
            rows_returned=len(result.get("rows", [])),
            success=True,
            error_message=None,
        )
        return {**state, "result": result}
    except Exception as exc:
        log_operation(
            session_id=state.get("session_id"),
            operation="query",
            question=state.get("question"),
            sql_text=sql,
            rows_returned=None,
            success=False,
            error_message=str(exc),
        )
        return {**state, "error": f"SQL execution failed: {exc}"}


def format_answer(state: AgentState) -> AgentState:
    try:
        result = state.get("result") or {"columns": [], "rows": []}
        preview = {
            "columns": result.get("columns", []),
            "rows": result.get("rows", [])[:_FORMAT_ROW_PREVIEW],
        }
        system = _FORMAT_PATH.read_text(encoding="utf-8").strip()
        user = "\n\n".join(
            [
                f"Question: {state.get('question', '')}",
                f"SQL: {state.get('sql_text', '')}",
                "Result rows (JSON):",
                json.dumps(preview, default=str),
            ]
        )
        answer = LLMClient().call_model(user, system=system)
        return {**state, "answer_text": answer.strip()}
    except Exception as exc:
        return {**state, "error": f"Answer formatting failed: {exc}"}


def handle_error(state: AgentState) -> AgentState:
    return {**state, "status": "failed"}


def finalize(state: AgentState) -> AgentState:
    return {**state, "status": "completed"}
