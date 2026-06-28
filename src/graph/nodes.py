"""LangGraph nodes for the CSV analyst: plan -> generate_code -> execute_code
-> finalize / handle_error.

The LLM is called ONLY in `plan` and `generate_code`, and both receive ONLY the
schema, the sample rows, the question, and (on retry) the prior error — never the
full data. See spec/agent.md#privacy-boundary.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from analyst.sandbox import run_code
from graph.events_bus import publish
from graph.state import AgentState
from llm.client import LLMClient
from observability.events import get_logger

_PROMPTS = Path(__file__).parent.parent / "prompts"
_log = get_logger("graph")

DEFAULT_MAX_RETRIES = 3
SANDBOX_TIMEOUT = 60
_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def _load(name: str) -> str:
    return (_PROMPTS / name).read_text(encoding="utf-8").strip()


def _schema_block(state: AgentState) -> str:
    schema = state.get("schema") or []
    sample = state.get("sample_rows") or []
    return (
        "Schema (column, dtype):\n"
        + "\n".join(f"- {c.get('name')}: {c.get('dtype')}" for c in schema)
        + "\n\nSample rows (<= 20, FOR REFERENCE ONLY — the full data is loaded for you):\n"
        + json.dumps(sample, ensure_ascii=False)
    )


def build_plan_prompt(state: AgentState) -> str:
    return (
        f"{_schema_block(state)}\n\n"
        f"Question: {state.get('question', '')}\n\n"
        "Write the short plan."
    )


def build_code_prompt(state: AgentState) -> str:
    parts = [_schema_block(state)]
    if state.get("plan"):
        parts.append(f"Plan:\n{state['plan']}")
    parts.append(f"Question: {state.get('question', '')}")
    if state.get("last_error"):
        parts.append(
            "The previous attempt FAILED with this error — fix the specific cause:\n"
            f"{state['last_error']}"
        )
    parts.append("Write the corrected pandas code as a single fenced block.")
    return "\n\n".join(parts)


def build_followups_prompt(state: AgentState) -> str:
    """Privacy-safe follow-ups prompt: schema (column,dtype) + question + a SHORT
    answer summary ONLY. Deliberately omits sample_rows and any full data —
    follow-ups are schema-only (see spec/agent.md#privacy-boundary)."""
    schema = state.get("schema") or []
    schema_block = "Schema (column, dtype):\n" + "\n".join(
        f"- {c.get('name')}: {c.get('dtype')}" for c in schema
    )
    answer = (state.get("answer") or "").strip()
    answer_summary = answer[:400]
    parts = [
        schema_block,
        f"Question just answered: {state.get('question', '')}",
    ]
    if answer_summary:
        parts.append(f"Answer summary: {answer_summary}")
    parts.append("Propose 2-3 follow-up questions as a JSON array of strings.")
    return "\n\n".join(parts)


def _parse_followups(text: str) -> list[str]:
    """Parse 2-3 follow-up strings from the model output.

    Accepts a JSON array first; falls back to line-by-line parsing. Returns at
    most 3 non-empty, de-duplicated questions; [] if nothing usable is found.
    """
    if not text:
        return []
    candidates: list[str] = []
    cleaned = text.strip()
    # Strip a markdown fence if the model wrapped the JSON.
    fenced = _FENCE_RE.search(cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()
    # Try JSON array.
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            arr = json.loads(cleaned[start:end + 1])
            if isinstance(arr, list):
                candidates = [str(x).strip() for x in arr if str(x).strip()]
        except (json.JSONDecodeError, ValueError):
            candidates = []
    # Fallback: one question per line.
    if not candidates:
        for line in cleaned.splitlines():
            line = line.strip().lstrip("-*0123456789. ").strip().strip('"')
            if line and len(line) > 3:
                candidates.append(line)

    out: list[str] = []
    for q in candidates:
        if q not in out:
            out.append(q)
    return out[:3]


def _parse_code(text: str) -> str:
    """Extract the first fenced code block; fall back to the raw text."""
    if not text:
        return ""
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def plan(state: AgentState) -> AgentState:
    started = time.monotonic()
    try:
        text, tokens = LLMClient().call_model_with_usage(
            build_plan_prompt(state), system=_load("plan.md")
        )
        plan_text = (text or "").strip()
        total_tokens = state.get("tokens", 0) + tokens
        latency = int((time.monotonic() - started) * 1000)
        _log.info("node", run_id=state.get("run_id"), node="plan",
                  latency_ms=latency, tokens=tokens)
        publish(state.get("run_id", ""), "plan", {"plan": plan_text})
        return {**state, "plan": plan_text, "tokens": total_tokens, "error": None}
    except Exception as exc:
        _log.error("node_error", run_id=state.get("run_id"), node="plan", error=str(exc))
        return {**state, "error": f"Planning failed: {exc}"}


def generate_code(state: AgentState) -> AgentState:
    started = time.monotonic()
    attempt = state.get("retries", 0) + 1
    phase_msg = "writing code" if attempt == 1 else f"rewriting code (retry {attempt - 1})"
    publish(state.get("run_id", ""), "step",
            {"phase": "generate_code", "attempt": attempt, "message": phase_msg})
    try:
        text, tokens = LLMClient().call_model_with_usage(
            build_code_prompt(state), system=_load("code.md")
        )
        code = _parse_code(text)
        if not code:
            return {**state, "error": "Model returned no code."}
        total_tokens = state.get("tokens", 0) + tokens
        latency = int((time.monotonic() - started) * 1000)
        _log.info("node", run_id=state.get("run_id"), node="generate_code",
                  attempt=attempt, latency_ms=latency, tokens=tokens)
        return {**state, "code": code, "tokens": total_tokens, "error": None}
    except Exception as exc:
        _log.error("node_error", run_id=state.get("run_id"),
                   node="generate_code", error=str(exc))
        return {**state, "error": f"Code generation failed: {exc}"}


def execute_code(state: AgentState) -> AgentState:
    run_id = state.get("run_id", "")
    attempt = state.get("retries", 0) + 1
    publish(run_id, "step",
            {"phase": "execute_code", "attempt": attempt, "message": "running code"})

    code = state.get("code") or ""
    csv_paths = state.get("csv_paths") or {}
    result = run_code(csv_paths, code, timeout=SANDBOX_TIMEOUT)

    attempts = list(state.get("attempts", []))
    attempts.append({
        "attempt": attempt,
        "code": code,
        "ok": result.ok,
        "error": result.error,
        "duration_ms": result.duration_ms,
    })

    _log.info("tool", run_id=run_id, node="execute_code", attempt=attempt,
              ok=result.ok, duration_ms=result.duration_ms,
              code_hash=hash(code) & 0xFFFFFFFF)

    if result.ok:
        return {
            **state,
            "attempts": attempts,
            "result": result.result,
            "chart_spec": result.chart_spec,
            "table": result.table if isinstance(result.table, list) else None,
            "last_error": None,
            "error": None,
        }

    # Failure — record, feed the error back, bump the retry counter.
    publish(run_id, "retry", {"attempt": attempt, "error": (result.error or "")[:600]})
    return {
        **state,
        "attempts": attempts,
        "last_error": result.error,
        "retries": state.get("retries", 0) + 1,
    }


def _compose_answer(state: AgentState) -> str:
    """Deterministic plain-English answer from the computed result (no LLM)."""
    result = state.get("result")
    question = state.get("question", "your question")

    if isinstance(result, dict):
        n = len(result)
        head = ", ".join(f"{k}: {v}" for k, v in list(result.items())[:5])
        more = "" if n <= 5 else f" (and {n - 5} more)"
        return (
            f'Here are the results for "{question}". '
            f"{n} group(s): {head}{more}."
        )
    if isinstance(result, list):
        return (
            f'Computed {len(result)} row(s) for "{question}". '
            "See the table below for the full breakdown."
        )
    if result is None:
        return f'The analysis ran for "{question}" but produced no value.'
    return f'The answer to "{question}" is: {result}.'


# Phrases that signal the model could not answer from THIS dataset (missing/unknown
# column, or an inability to answer). Kept conservative + anchored so a legitimate
# textual answer that merely mentions the word "column" still succeeds.
_UNANSWERABLE_PHRASES = (
    "column not available",
    "not available in this dataset",
    "not available in the dataset",
    "no such column",
    "unknown column",
    "column not found",
    "column does not exist",
    "not in this dataset",
    "not in the dataset",
    "cannot be answered from this dataset",
    "cannot answer from this dataset",
    "can't be answered from this dataset",
    "cannot answer this question from this dataset",
    "not present in this dataset",
)


def _is_unanswerable_result(result: object) -> bool:
    """Conservatively detect a degenerate "can't answer from this dataset" result.

    Only string results qualify. We match on anchored, specific signals so a
    normal textual answer that merely contains the word "column" still succeeds:
      - a string that starts with "Error:" (the model self-reporting a failure), or
      - a string containing one of the explicit unavailability phrases.
    """
    if not isinstance(result, str):
        return False
    text = result.strip().lower()
    if not text:
        return False
    if text.startswith("error:"):
        return True
    return any(phrase in text for phrase in _UNANSWERABLE_PHRASES)


def _available_columns(state: AgentState) -> list[str]:
    schema = state.get("schema") or []
    cols = [str(c.get("name")) for c in schema if c.get("name") is not None]
    return cols


def _unanswerable_message(state: AgentState) -> str:
    cols = _available_columns(state)
    cols_str = ", ".join(cols) if cols else "(none detected)"
    return (
        "This question can't be answered from the loaded dataset. "
        f"Available columns: {cols_str}. "
        "(Cross-file analysis to answer this is coming in a later phase.)"
    )


def _to_jsonable(obj: object) -> object:
    """Best-effort JSON-safe coercion in the PARENT process for synthesized tables.

    The sandbox already coerces its payloads; this guards values we build here
    (NaN -> None, numpy scalars -> python). Falls back to str() for the exotic.
    """
    try:
        import math

        import numpy as np
        import pandas as pd
    except Exception:  # pragma: no cover - pandas/numpy always present in this app
        np = None
        pd = None
        import math

    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        return None if math.isnan(obj) else obj
    if np is not None:
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            val = float(obj)
            return None if math.isnan(val) else val
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return [_to_jsonable(x) for x in obj.tolist()]
    if pd is not None:
        if isinstance(obj, pd.Series):
            return {str(_to_jsonable(k)): _to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, pd.DataFrame):
            recs = obj.astype(object).where(pd.notnull(obj), None).to_dict(orient="records")
            return [{str(k): _to_jsonable(v) for k, v in r.items()} for r in recs]
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    try:
        return _to_jsonable(obj.item())  # numpy/pandas scalar wrapper
    except Exception:
        return str(obj)


def _metric_label(state: AgentState) -> str:
    """A sensible single-column label for a synthesized scalar table."""
    question = (state.get("question") or "").strip()
    return question[:60] if question else "result"


def synthesize_table(state: AgentState) -> list[dict] | None:
    """Deterministically build a summary table from `result` when the code did
    not assign one. Every successful answer must carry a table (spec/agent.md
    finalize rule). Returns JSON-safe records, or None if nothing usable.

    Shapes:
      - scalar (int/float/str/bool/np scalar) -> [{<metric-label>: value}]
      - dict / Series                         -> [{"key": k, "value": v}, ...]
      - list of records / DataFrame-records   -> pass through unchanged
    """
    result = state.get("result")
    if result is None:
        return None

    safe = _to_jsonable(result)

    # Already a list of record dicts (DataFrame-records / passthrough).
    if isinstance(safe, list):
        if safe and all(isinstance(r, dict) for r in safe):
            return safe
        if not safe:
            return None
        # A plain list of scalars -> one column.
        return [{"value": v} for v in safe]

    # dict / Series -> key/value records.
    if isinstance(safe, dict):
        if not safe:
            return None
        return [{"key": str(k), "value": v} for k, v in safe.items()]

    # Scalar -> one-row, one-cell table.
    return [{_metric_label(state): safe}]


def finalize(state: AgentState) -> AgentState:
    result = state.get("result")

    # Defect 2: a degenerate "can't answer from this dataset" result must NOT be
    # reported as a green success. Route it to the failure channel with the list
    # of columns that ARE available, so the frontend FailureCard renders it.
    if _is_unanswerable_result(result):
        message = _unanswerable_message(state)
        _log.info("node", run_id=state.get("run_id"), node="finalize",
                  status="failed", reason="unanswerable")
        return {**state, "answer": None, "status": "failed", "error": message}

    answer = _compose_answer(state)

    # Defect 1: every successful answer carries a summary table. If the code did
    # not assign one, synthesize it deterministically from `result`.
    table = state.get("table")
    if not table:
        table = synthesize_table(state)

    _log.info("node", run_id=state.get("run_id"), node="finalize", status="completed",
              table_rows=len(table) if table else 0)
    return {**state, "answer": answer, "table": table, "status": "completed", "error": None}


def suggest_followups(state: AgentState) -> AgentState:
    """Cheap, schema-only LLM call proposing 2-3 follow-up questions after a
    successful run. Best-effort: any failure degrades to [] and never fails the
    run (per the capability's "follow-ups omitted; answer still returned")."""
    started = time.monotonic()
    run_id = state.get("run_id", "")
    try:
        text, tokens = LLMClient().call_model_with_usage(
            build_followups_prompt(state), system=_load("followups.md")
        )
        followups = _parse_followups(text)
        total_tokens = state.get("tokens", 0) + tokens
        latency = int((time.monotonic() - started) * 1000)
        _log.info("node", run_id=run_id, node="suggest_followups",
                  latency_ms=latency, tokens=tokens, count=len(followups))
        return {**state, "followups": followups, "tokens": total_tokens}
    except Exception as exc:
        latency = int((time.monotonic() - started) * 1000)
        _log.error("node_error", run_id=run_id, node="suggest_followups",
                   latency_ms=latency, error=str(exc))
        return {**state, "followups": []}


def handle_error(state: AgentState) -> AgentState:
    retries = state.get("retries", 0)
    err = state.get("error") or state.get("last_error") or "unknown error"
    if state.get("error"):
        message = err
    else:
        message = f"gave up after {retries} attempt(s): {err}"
    _log.error("node", run_id=state.get("run_id"), node="handle_error",
               status="failed", error=message)
    return {**state, "status": "failed", "error": message}
