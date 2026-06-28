"""The Local Data Analyst pipeline nodes (see spec/agent.md).

Each node is pure-ish: it reads from and returns an ``AnalystState`` patch.
LLM nodes go through ``LLMClient`` (never the SDK directly) and log the full
prompt for the privacy audit. SQL execution goes through ``analysis.execute_sql``
locally. SQL execution errors set ``sql_error`` (drives the retry loop), NOT
``error``; LLM/guard failures set ``error`` (routes to handle_error).
"""
import json
import re
import time
from pathlib import Path

from analysis import execute_sql as run_duckdb_sql
from analysis import pick_chart as pick_chart_heuristic
from analysis import to_aggregate
from graph.state import AGG_ROW_CAP, MAX_SQL_RETRIES, AnalystState
from llm.client import LLMClient
from observability.events import log_llm_call, log_step

_PROMPTS = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS / name).read_text(encoding="utf-8").strip()


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def _parse_json(text: str) -> dict:
    """Parse a model response defensively: strip markdown fences, find the JSON
    object, and load it. Raises ValueError if nothing parseable is found.
    """
    if text is None:
        raise ValueError("empty model response")
    cleaned = text.strip()
    # strip ```json ... ``` or ``` ... ``` fences
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # fall back to the first {...} block
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start : end + 1])
    raise ValueError(f"could not parse JSON from model response: {cleaned[:200]!r}")


def _append_trace(state: AnalystState, entry: dict) -> list:
    trace = list(state.get("trace") or [])
    trace.append(entry)
    return trace


def _call_llm(state: AnalystState, *, node: str, system: str, prompt: str) -> tuple[str, float]:
    """Call the LLM, log the call (full prompt for the privacy audit), return
    (text, cost_usd)."""
    client = LLMClient()
    started = _now_ms()
    result = client.call_model_usage(prompt, system=system)
    latency_ms = _now_ms() - started
    log_llm_call(
        run_id=state.get("run_id"),
        node=node,
        model=client.model,
        prompt=prompt,
        system=system,
        output=result.text,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        latency_ms=latency_ms,
        cost_usd=result.cost_usd,
    )
    return result.text, result.cost_usd


def _schema_text(schema: dict) -> str:
    """Render the schema (columns + types + health summary) as text. NO raw rows."""
    return json.dumps(schema, default=str)


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #


def plan(state: AnalystState) -> AnalystState:
    """Produce a plan + first DuckDB SQL candidate. Schema-only LLM payload."""
    started = _now_ms()
    try:
        system = _load_prompt("plan.md")
        prompt = (
            f"Question: {state['question']}\n\n"
            f"Schema (no rows):\n{_schema_text(state['schema'])}"
        )
        text, cost = _call_llm(state, node="plan", system=system, prompt=prompt)
        parsed = _parse_json(text)
        plan_text = str(parsed.get("plan", "")).strip()
        sql = str(parsed.get("sql", "")).strip()
        if not sql:
            raise ValueError("plan produced no SQL")
        latency_ms = _now_ms() - started
        log_step(run_id=state.get("run_id"), step="plan", ok=True, latency_ms=latency_ms)
        return {
            **state,
            "plan": plan_text,
            "sql": sql,
            "phase": "pre",
            "sql_attempts": int(state.get("sql_attempts") or 0),
            "cost_usd": float(state.get("cost_usd") or 0.0) + cost,
            "trace": _append_trace(
                state, {"step": "plan", "ok": True, "latency_ms": latency_ms}
            ),
        }
    except Exception as exc:  # LLM / parse failure -> fatal
        latency_ms = _now_ms() - started
        log_step(
            run_id=state.get("run_id"),
            step="plan",
            ok=False,
            latency_ms=latency_ms,
            error=str(exc),
        )
        return {
            **state,
            "error": f"plan failed: {exc}",
            "trace": _append_trace(
                state,
                {"step": "plan", "ok": False, "error": str(exc), "latency_ms": latency_ms},
            ),
        }


def privacy_guard(state: AnalystState) -> AnalystState:
    """The single chokepoint for result data going to the LLM.

    Pre-execute pass (phase != "post"): pass through to execute_sql; the plan
    call already used schema only.

    Post-execute pass (phase == "post"): build the bounded ``aggregate`` from the
    full local ``result`` via ``to_aggregate`` (capped at AGG_ROW_CAP). This is
    the ONLY result data that may reach the phrasing LLM call.
    """
    started = _now_ms()
    # pre-execute pass: nothing to bound yet
    if state.get("phase") != "post":
        return {**state}
    try:
        result = state.get("result") or {"columns": [], "rows": []}
        aggregate = to_aggregate(result, cap=AGG_ROW_CAP)
        latency_ms = _now_ms() - started
        truncated = bool(aggregate.get("truncated"))
        entry = {"step": "guard", "ok": True, "latency_ms": latency_ms}
        if truncated:
            entry["note"] = "truncated"
        log_step(
            run_id=state.get("run_id"),
            step="guard",
            ok=True,
            latency_ms=latency_ms,
            error="truncated" if truncated else None,
        )
        return {
            **state,
            "aggregate": aggregate,
            "trace": _append_trace(state, entry),
        }
    except Exception as exc:
        latency_ms = _now_ms() - started
        log_step(
            run_id=state.get("run_id"),
            step="guard",
            ok=False,
            latency_ms=latency_ms,
            error=str(exc),
        )
        return {
            **state,
            "error": f"privacy_guard failed: {exc}",
            "trace": _append_trace(
                state,
                {"step": "guard", "ok": False, "error": str(exc), "latency_ms": latency_ms},
            ),
        }


def generate_sql(state: AnalystState) -> AnalystState:
    """Retry regeneration: feed the failed SQL + exact DuckDB error back to the
    model for corrected SQL. Schema + error only — no rows."""
    started = _now_ms()
    try:
        system = _load_prompt("generate_sql.md")
        prompt = (
            f"Question: {state['question']}\n\n"
            f"Schema (no rows):\n{_schema_text(state['schema'])}\n\n"
            f"The SQL that failed:\n{state.get('sql', '')}\n\n"
            f"The exact DuckDB error:\n{state.get('sql_error', '')}"
        )
        text, cost = _call_llm(state, node="generate_sql", system=system, prompt=prompt)
        parsed = _parse_json(text)
        sql = str(parsed.get("sql", "")).strip()
        if not sql:
            raise ValueError("retry produced no SQL")
        latency_ms = _now_ms() - started
        log_step(run_id=state.get("run_id"), step="retry", ok=True, latency_ms=latency_ms)
        return {
            **state,
            "sql": sql,
            "cost_usd": float(state.get("cost_usd") or 0.0) + cost,
            "trace": _append_trace(
                state, {"step": "retry", "ok": True, "sql": sql, "latency_ms": latency_ms}
            ),
        }
    except Exception as exc:
        latency_ms = _now_ms() - started
        log_step(
            run_id=state.get("run_id"),
            step="retry",
            ok=False,
            latency_ms=latency_ms,
            error=str(exc),
        )
        return {
            **state,
            "error": f"generate_sql failed: {exc}",
            "trace": _append_trace(
                state,
                {"step": "retry", "ok": False, "error": str(exc), "latency_ms": latency_ms},
            ),
        }


def execute_sql(state: AnalystState) -> AnalystState:
    """Run the candidate SQL locally against DuckDB.

    Success: set ``result``, clear ``sql_error``. Failure: capture the exact
    DuckDB error in ``sql_error``, increment ``sql_attempts`` (NOT ``error``) so
    the retry edge engages.
    """
    started = _now_ms()
    attempts = int(state.get("sql_attempts") or 0) + 1
    sql = state.get("sql", "")
    table_name = state.get("table_name", "t")
    try:
        result = run_duckdb_sql(state["dataset_path"], sql, table_name=table_name)
        latency_ms = _now_ms() - started
        log_step(run_id=state.get("run_id"), step="execute", ok=True, latency_ms=latency_ms)
        return {
            **state,
            "result": result,
            "sql_error": None,
            "sql_attempts": attempts,
            "phase": "post",
            "trace": _append_trace(
                state, {"step": "execute", "ok": True, "latency_ms": latency_ms}
            ),
        }
    except Exception as exc:
        latency_ms = _now_ms() - started
        err = str(exc)
        log_step(
            run_id=state.get("run_id"),
            step="execute",
            ok=False,
            latency_ms=latency_ms,
            error=err,
        )
        return {
            **state,
            "sql_error": err,
            "sql_attempts": attempts,
            "trace": _append_trace(
                state,
                {"step": "execute", "ok": False, "error": err, "latency_ms": latency_ms},
            ),
        }


def phrase_answer(state: AnalystState) -> AnalystState:
    """Phrase a concise answer from the bounded aggregate ONLY."""
    started = _now_ms()
    try:
        aggregate = state.get("aggregate") or {"columns": [], "rows": []}
        system = _load_prompt("phrase_answer.md")
        prompt = (
            f"Question: {state['question']}\n\n"
            f"Plan: {state.get('plan', '')}\n\n"
            f"Aggregated result (bounded, this is the only data you get):\n"
            f"{json.dumps(aggregate, default=str)}"
        )
        text, cost = _call_llm(state, node="phrase_answer", system=system, prompt=prompt)
        parsed = _parse_json(text)
        answer = str(parsed.get("answer", "")).strip()
        key_numbers = parsed.get("key_numbers") or []
        if not answer:
            raise ValueError("phrasing produced no answer")
        latency_ms = _now_ms() - started
        log_step(run_id=state.get("run_id"), step="phrase", ok=True, latency_ms=latency_ms)
        return {
            **state,
            "answer": answer,
            "key_numbers": key_numbers,
            "cost_usd": float(state.get("cost_usd") or 0.0) + cost,
            "trace": _append_trace(
                state, {"step": "phrase", "ok": True, "latency_ms": latency_ms}
            ),
        }
    except Exception as exc:
        latency_ms = _now_ms() - started
        log_step(
            run_id=state.get("run_id"),
            step="phrase",
            ok=False,
            latency_ms=latency_ms,
            error=str(exc),
        )
        return {
            **state,
            "error": f"phrase_answer failed: {exc}",
            "trace": _append_trace(
                state,
                {"step": "phrase", "ok": False, "error": str(exc), "latency_ms": latency_ms},
            ),
        }


def pick_chart(state: AnalystState) -> AnalystState:
    """Deterministic chart pick from the aggregate. Degrades gracefully on error."""
    started = _now_ms()
    try:
        aggregate = state.get("aggregate") or {"columns": [], "rows": []}
        chart = pick_chart_heuristic(aggregate)
        latency_ms = _now_ms() - started
        log_step(run_id=state.get("run_id"), step="chart", ok=True, latency_ms=latency_ms)
        return {
            **state,
            "chart": chart,
            "trace": _append_trace(
                state, {"step": "chart", "ok": True, "latency_ms": latency_ms}
            ),
        }
    except Exception as exc:  # chart is non-critical — degrade, don't fail the run
        latency_ms = _now_ms() - started
        log_step(
            run_id=state.get("run_id"),
            step="chart",
            ok=False,
            latency_ms=latency_ms,
            error=str(exc),
        )
        return {
            **state,
            "chart": {"type": "table"},
            "trace": _append_trace(
                state,
                {"step": "chart", "ok": False, "error": str(exc), "latency_ms": latency_ms},
            ),
        }


def finalize(state: AnalystState) -> AnalystState:
    """Mark success. The runner persists the question_runs row after return."""
    return {**state, "status": "completed"}


def handle_error(state: AnalystState) -> AnalystState:
    """Terminal failure. Compose the message (LLM error, or exhausted SQL retries)."""
    if state.get("error"):
        message = state["error"]
    elif state.get("sql_error"):
        attempts = int(state.get("sql_attempts") or 0)
        message = (
            f"SQL could not be corrected after {attempts} attempts: "
            f"{state.get('sql_error')}"
        )
    else:
        message = "unknown error"
    return {**state, "status": "failed", "error": message}
