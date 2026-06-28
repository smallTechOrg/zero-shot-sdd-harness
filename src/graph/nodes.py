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


def finalize(state: AgentState) -> AgentState:
    answer = _compose_answer(state)
    _log.info("node", run_id=state.get("run_id"), node="finalize", status="completed")
    return {**state, "answer": answer, "status": "completed", "error": None}


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
