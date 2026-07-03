"""LangGraph nodes for the data-analysis agent.

Each node takes the ``AgentState`` and returns a partial state update. LLM nodes
(``generate_code``, ``write_answer``) call Gemini through the ``LLMClient``
wrapper and set ``error`` on failure so the graph routes to ``handle_error``.
``execute_code`` is deliberately non-fatal: a code error becomes ``exec_error``
which drives the bounded retry loop.

Privacy discipline: ``load_context`` NEVER loads raw rows into state — only the
stored profile's schema + a few sample rows. Only schema + sample rows +
question (+ prior error on retry) are ever sent to the LLM. The full dataset is
read only inside the ``execute_code`` subprocess.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from graph.state import AgentState
from llm.client import LLMClient
from config.settings import get_settings
from db.session import create_db_session
from db.models import DatasetRow, RunRow
from analysis.executor import run_pandas
from analysis.charts import build_vega_spec
from observability.events import get_logger

_PROMPTS = Path(__file__).parent.parent / "prompts"
_log = get_logger("graph")


def _load_prompt(name: str) -> str:
    return (_PROMPTS / name).read_text(encoding="utf-8")


def _fill(template: str, **tokens: str) -> str:
    """Fill ``{name}`` placeholders WITHOUT str.format — the prompts contain
    literal ``{``/``}`` braces in their JSON examples that must be left intact."""
    for key, value in tokens.items():
        template = template.replace("{" + key + "}", str(value))
    return template


# --------------------------------------------------------------------------- #
# load_context
# --------------------------------------------------------------------------- #
def load_context(state: AgentState) -> AgentState:
    run_id = state.get("run_id")
    dataset_id = state.get("dataset_id")
    try:
        with create_db_session() as session:
            ds = session.get(DatasetRow, dataset_id)
            if ds is None:
                _log.warning("load_context.dataset_missing", run_id=run_id, dataset_id=dataset_id)
                return {**state, "error": f"Dataset {dataset_id} not found."}

            profile = json.loads(ds.profile_json) if ds.profile_json else {}
            columns = profile.get("columns", []) or []
            schema = [
                {
                    "name": c.get("name"),
                    "dtype": c.get("dtype"),
                    "null_count": c.get("null_count"),
                }
                for c in columns
            ]
            sample_rows = profile.get("sample_rows", []) or []
            row_count = ds.row_count
            data_path = ds.file_path
            file_format = ds.file_format

        _log.info("load_context.ok", run_id=run_id, dataset_id=dataset_id, row_count=row_count)
        return {
            **state,
            "schema": schema,
            "sample_rows": sample_rows,
            "row_count": row_count,
            "data_path": data_path,
            "file_format": file_format,
            "attempts": 0,
        }
    except Exception as exc:  # noqa: BLE001
        _log.error("load_context.error", run_id=run_id, error=str(exc))
        return {**state, "error": f"Failed to load dataset context: {exc}"}


# --------------------------------------------------------------------------- #
# generate_code
# --------------------------------------------------------------------------- #
_CODE_FENCE_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_code(text: str) -> str:
    """Pull the fenced python block; fall back to raw text if unfenced."""
    matches = _CODE_FENCE_RE.findall(text or "")
    for block in matches:
        if "result" in block:
            return block.strip()
    if matches:
        return matches[0].strip()
    # No fence — accept raw text only if it assigns result.
    if "result" in (text or "") and "=" in (text or ""):
        return text.strip()
    return ""


def _format_schema(schema: list[dict]) -> str:
    lines = []
    for c in schema:
        lines.append(f"  - {c.get('name')} — {c.get('dtype')} — {c.get('null_count')} nulls")
    return "\n".join(lines) if lines else "  (no columns)"


def generate_code(state: AgentState) -> AgentState:
    run_id = state.get("run_id")
    attempts = state.get("attempts", 0) + 1

    retry_section = ""
    exec_error = state.get("exec_error")
    prior_code = state.get("code")
    if exec_error and prior_code:
        retry_section = (
            "\n## Previous attempt FAILED — fix it\n\n"
            "Your previous code raised this error:\n\n"
            f"```\n{exec_error}\n```\n\n"
            "Here is the code that failed:\n\n"
            f"```python\n{prior_code}\n```\n\n"
            "Return a corrected version that does not raise."
        )

    prompt = _fill(
        _load_prompt("generate_code.md"),
        row_count=state.get("row_count", "unknown"),
        schema=_format_schema(state.get("schema", [])),
        sample_rows=json.dumps(state.get("sample_rows", []), default=str, indent=2),
        question=state.get("question", ""),
        retry_section=retry_section,
    )

    try:
        _log.info("generate_code.call", run_id=run_id, attempt=attempts)
        raw = LLMClient().call_model(prompt)
        code = _extract_code(raw)
        if not code:
            _log.warning("generate_code.no_code", run_id=run_id, attempt=attempts)
            return {
                **state,
                "attempts": attempts,
                "error": "The model did not return a usable pandas code block.",
            }
        _log.info("generate_code.ok", run_id=run_id, attempt=attempts, code_len=len(code))
        return {**state, "code": code, "attempts": attempts}
    except Exception as exc:  # noqa: BLE001
        _log.error("generate_code.error", run_id=run_id, error=str(exc))
        return {**state, "attempts": attempts, "error": f"Code generation failed: {exc}"}


# --------------------------------------------------------------------------- #
# execute_code
# --------------------------------------------------------------------------- #
def execute_code(state: AgentState) -> AgentState:
    run_id = state.get("run_id")
    settings = get_settings()
    result, error = run_pandas(
        state.get("code", ""),
        state.get("data_path", ""),
        state.get("file_format", ""),
        settings.exec_timeout_seconds,
    )
    if error:
        _log.warning(
            "execute_code.exec_error",
            run_id=run_id,
            attempt=state.get("attempts"),
            error=error[:500],
        )
        return {**state, "exec_error": error, "exec_result": None}

    _log.info("execute_code.ok", run_id=run_id, attempt=state.get("attempts"))
    return {**state, "exec_result": result, "exec_error": None}


# --------------------------------------------------------------------------- #
# write_answer
# --------------------------------------------------------------------------- #
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _parse_answer_json(text: str) -> dict:
    """Tolerantly parse the answer JSON object from the model output."""
    candidates: list[str] = []
    for block in _JSON_FENCE_RE.findall(text or ""):
        candidates.append(block.strip())
    stripped = (text or "").strip()
    candidates.append(stripped)
    # First { ... last } slice as a last resort.
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(stripped[start : end + 1])

    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, TypeError):
            continue
    raise ValueError("Could not parse a JSON answer object from the model output.")


def _coerce_key_numbers(raw) -> list[dict]:
    out: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                out.append(
                    {
                        "label": str(item.get("label", "")),
                        "value": str(item.get("value", "")),
                    }
                )
    return out


def write_answer(state: AgentState) -> AgentState:
    run_id = state.get("run_id")
    exec_result = state.get("exec_result") or {}
    table = exec_result.get("table", []) or []

    prompt = _fill(
        _load_prompt("write_answer.md"),
        question=state.get("question", ""),
        result_json=json.dumps(exec_result, default=str, indent=2),
    )

    try:
        _log.info("write_answer.call", run_id=run_id)
        raw = LLMClient().call_model(prompt)
        parsed = _parse_answer_json(raw)
    except Exception as exc:  # noqa: BLE001
        _log.error("write_answer.error", run_id=run_id, error=str(exc))
        return {**state, "error": f"Answer composition failed: {exc}"}

    answer_text = str(parsed.get("answer", "") or "")
    narrative = str(parsed.get("narrative", "") or "")
    key_numbers = _coerce_key_numbers(parsed.get("key_numbers"))
    chart_selection = parsed.get("chart") if isinstance(parsed.get("chart"), dict) else {}

    # An invalid chart selection must NOT fail the run — build_vega_spec falls back.
    chart_spec = build_vega_spec(chart_selection, table)

    _log.info("write_answer.ok", run_id=run_id, key_numbers=len(key_numbers))
    return {
        **state,
        "answer_text": answer_text,
        "narrative": narrative,
        "key_numbers": key_numbers,
        "chart_spec": chart_spec,
        "table": table,
    }


# --------------------------------------------------------------------------- #
# finalize
# --------------------------------------------------------------------------- #
def _dumps(value) -> str:
    return json.dumps(value, default=str)


def finalize(state: AgentState) -> AgentState:
    run_id = state.get("run_id")
    try:
        with create_db_session() as session:
            run = session.get(RunRow, run_id)
            if run is not None:
                run.status = "completed"
                run.generated_code = state.get("code")
                run.result_json = _dumps(state.get("exec_result"))
                run.answer_text = state.get("answer_text")
                run.narrative = state.get("narrative")
                run.key_numbers_json = _dumps(state.get("key_numbers", []))
                run.chart_json = _dumps(state.get("chart_spec", {}))
                run.table_json = _dumps(state.get("table", []))
                run.attempts = state.get("attempts", 0)
        _log.info("finalize.ok", run_id=run_id, attempts=state.get("attempts"))
    except Exception as exc:  # noqa: BLE001
        _log.error("finalize.error", run_id=run_id, error=str(exc))
    return {**state, "status": "completed"}


# --------------------------------------------------------------------------- #
# handle_error
# --------------------------------------------------------------------------- #
def handle_error(state: AgentState) -> AgentState:
    run_id = state.get("run_id")
    error = state.get("error") or state.get("exec_error") or "Unknown error"
    _log.error("handle_error", run_id=run_id, error=str(error), attempts=state.get("attempts"))
    try:
        with create_db_session() as session:
            run = session.get(RunRow, run_id)
            if run is not None:
                run.status = "failed"
                run.error_message = str(error)
                run.generated_code = state.get("code")
                run.attempts = state.get("attempts", 0)
    except Exception as exc:  # noqa: BLE001
        _log.error("handle_error.persist_failed", run_id=run_id, error=str(exc))
    return {**state, "status": "failed", "error": str(error)}
