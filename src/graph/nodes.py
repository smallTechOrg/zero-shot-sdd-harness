"""Agent nodes for the data-analysis loop.

Each node wraps its body in try/except and sets ``state["error"]`` on a fatal
failure (routed to ``handle_error``). LLM nodes build their prompt through the
privacy gate (``llm.payload.build``) so raw rows can never reach the model.
User-code execution errors are NOT fatal — they are fed to ``inspect`` to drive
a refine.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from analysis import executor
from analysis.dataset_store import get_dataset_store
from config.settings import get_settings
from graph.state import AgentState
from llm import payload
from llm.client import LLMClient
from observability.events import get_logger

_log = get_logger("agent.node")
_PROMPT_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8").strip()


import re

# Valid JSON escape leaders: \" \\ \/ \b \f \n \r \t \uXXXX.
_VALID_ESCAPE = re.compile(r'\\(["\\/bfnrt]|u[0-9a-fA-F]{4})')


def _repair_escapes(text: str) -> str:
    """Escape lone backslashes the model emitted inside JSON string values.

    Gemini sometimes returns pandas code (regex, ``\\d``, Windows paths) inside a
    JSON ``code`` field with backslashes that aren't valid JSON escapes. We
    double any backslash that isn't the start of a valid JSON escape sequence so
    ``json.loads`` succeeds and the original code text is preserved.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            if _VALID_ESCAPE.match(text, i):
                out.append(text[i : i + 2])
                i += 2
                continue
            out.append("\\\\")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _loads(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_repair_escapes(text))


def _parse_json(text: str) -> dict[str, Any]:
    """Parse a JSON object from an LLM response, tolerating code fences and
    lone backslashes in code/string values."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        return _loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return _loads(cleaned[start : end + 1])
        raise


def _accumulate(state: AgentState, prompt_tokens: int, completion_tokens: int) -> None:
    """Add token usage to the cumulative tally and recompute cost."""
    tokens = dict(state.get("tokens") or {"prompt": 0, "completion": 0})
    tokens["prompt"] = int(tokens.get("prompt", 0)) + int(prompt_tokens)
    tokens["completion"] = int(tokens.get("completion", 0)) + int(completion_tokens)
    state["tokens"] = tokens
    s = get_settings()
    state["cost_usd"] = round(
        (tokens["prompt"] / 1000.0) * s.cost_per_1k_in
        + (tokens["completion"] / 1000.0) * s.cost_per_1k_out,
        6,
    )


def _call_llm(state: AgentState, *, system: str, prompt: str) -> dict[str, Any]:
    """Call Gemini in JSON mode, accumulate tokens, return the parsed object."""
    result = LLMClient().generate(prompt, system=system, json_mode=True)
    _accumulate(state, result.prompt_tokens, result.completion_tokens)
    return _parse_json(result.text)


# --- Nodes ------------------------------------------------------------------


def node_plan(state: AgentState) -> AgentState:
    try:
        state["step_index"] = int(state.get("step_index", 0)) + 1
        prompt = payload.build(
            question=state.get("question"),
            messages=state.get("messages"),
            profile=state.get("profile"),
        )
        data = _call_llm(state, system=_load_prompt("plan.md"), prompt=prompt)
        needs = bool(data.get("needs_clarification", False))
        state["needs_clarification"] = needs
        state["plan"] = str(data.get("plan", ""))
        state["clarifying_question"] = data.get("clarifying_question") or None
        _log.info("node_plan", run_id=state.get("run_id"), needs_clarification=needs)
        return state
    except Exception as exc:  # fatal
        state["error"] = f"plan failed: {exc}"
        return state


def node_clarify(state: AgentState) -> AgentState:
    # No LLM — surface the clarifying question and end the run.
    state["status"] = "needs_clarification"
    state["prose"] = state.get("clarifying_question") or "Could you clarify your question?"
    _log.info("node_clarify", run_id=state.get("run_id"))
    return state


def node_generate_code(state: AgentState) -> AgentState:
    try:
        state["step_index"] = int(state.get("step_index", 0)) + 1
        prior = state.get("exec_result") or {}
        prompt = payload.build(
            question=state.get("question"),
            plan=state.get("plan"),
            profile=state.get("profile"),
            code=state.get("code") if prior.get("error") else None,
            result_summary=prior.get("summary"),
            extra={"prior_error": prior.get("error")} if prior.get("error") else None,
        )
        data = _call_llm(state, system=_load_prompt("generate_code.md"), prompt=prompt)
        code = str(data.get("code", "")).strip()
        if not code:
            raise ValueError("LLM returned empty code")
        state["code"] = code
        _log.info("node_generate_code", run_id=state.get("run_id"), step=state["step_index"])
        return state
    except Exception as exc:  # fatal
        state["error"] = f"generate_code failed: {exc}"
        return state


def node_execute(state: AgentState) -> AgentState:
    try:
        store = get_dataset_store()
        df = store.get(state["dataset_id"])
        if df is None:
            # Fatal: the frame must have been loaded at upload time.
            state["error"] = f"dataset {state['dataset_id']!r} not loaded in store"
            return state
        # Runs on the FULL DataFrame — never a sample.
        result = executor.run(state.get("code", ""), {"df": df})
        state["exec_result"] = result
        _log.info(
            "node_execute",
            run_id=state.get("run_id"),
            ok=result.get("error") is None,
            error=result.get("error"),
        )
        return state
    except Exception as exc:  # fatal (infra, not user-code)
        state["error"] = f"execute failed: {exc}"
        return state


def node_inspect(state: AgentState) -> AgentState:
    try:
        step = int(state.get("step_index", 0))
        max_steps = int(state.get("max_steps", get_settings().max_steps))
        exec_result = state.get("exec_result") or {}

        # Force finish when the step budget is exhausted.
        if step >= max_steps:
            state["_inspect_decision"] = "finish"
            state["_forced_finish"] = True
            _log.info("node_inspect", run_id=state.get("run_id"), decision="finish (max steps)")
            return state

        prompt = payload.build(
            question=state.get("question"),
            plan=state.get("plan"),
            code=state.get("code"),
            result_summary=exec_result.get("summary"),
            extra={"execution_error": exec_result.get("error")} if exec_result.get("error") else None,
        )
        data = _call_llm(state, system=_load_prompt("inspect.md"), prompt=prompt)
        decision = str(data.get("decision", "finish")).lower()
        if decision not in ("finish", "refine"):
            decision = "finish"
        state["_inspect_decision"] = decision
        _log.info("node_inspect", run_id=state.get("run_id"), decision=decision)
        return state
    except Exception as exc:  # fatal
        state["error"] = f"inspect failed: {exc}"
        return state


def node_finalize(state: AgentState) -> AgentState:
    try:
        exec_result = state.get("exec_result") or {}
        summary = exec_result.get("summary")
        forced = bool(state.get("_forced_finish"))

        extra: dict[str, Any] = {}
        if forced:
            extra["uncertainty_note"] = (
                "Hit the step limit — this is the best available result."
            )
        if exec_result.get("error"):
            extra["last_error"] = exec_result.get("error")

        prompt = payload.build(
            question=state.get("question"),
            plan=state.get("plan"),
            code=state.get("code"),
            result_summary=summary,
            extra=extra or None,
        )
        data = _call_llm(state, system=_load_prompt("finalize.md"), prompt=prompt)

        prose = str(data.get("prose", "")).strip()
        if forced and "step limit" not in prose.lower():
            prose = f"{prose} (Note: hit the step limit — best available result.)".strip()
        state["prose"] = prose or "No answer could be composed."
        state["chart"] = _build_chart(data.get("chart"), summary)
        state["table"] = _build_table(summary)
        state["follow_ups"] = list(data.get("follow_ups") or [])[:3]
        state["status"] = "completed"
        _log.info(
            "node_finalize",
            run_id=state.get("run_id"),
            cost_usd=state.get("cost_usd"),
            tokens=state.get("tokens"),
        )
        return state
    except Exception as exc:  # fatal
        state["error"] = f"finalize failed: {exc}"
        return state


def node_handle_error(state: AgentState) -> AgentState:
    state["status"] = "failed"
    _log.error("node_handle_error", run_id=state.get("run_id"), error=state.get("error"))
    return state


# --- finalize helpers -------------------------------------------------------


def _build_table(summary: dict | None) -> dict | None:
    """Build a results table (columns + rows) from the AGGREGATE result summary."""
    if not summary:
        return None
    kind = summary.get("kind")
    if kind == "dataframe":
        cols = list(summary.get("columns", []))
        rows = [[row.get(c) for c in cols] for row in summary.get("rows", [])]
        return {"columns": cols, "rows": rows, "truncated": summary.get("truncated", False)}
    if kind == "series":
        idx_name = summary.get("index_name") or "index"
        val_name = summary.get("name") or "value"
        rows = [[it.get("index"), it.get("value")] for it in summary.get("items", [])]
        return {"columns": [idx_name, val_name], "rows": rows, "truncated": summary.get("truncated", False)}
    if kind == "scalar":
        return {"columns": ["value"], "rows": [[summary.get("value")]], "truncated": False}
    if kind == "dict":
        items = summary.get("value", {})
        return {"columns": ["key", "value"], "rows": [[k, v] for k, v in items.items()], "truncated": False}
    if kind == "list":
        return {"columns": ["value"], "rows": [[v] for v in summary.get("value", [])], "truncated": False}
    return None


def _build_chart(chart_spec: Any, summary: dict | None) -> dict | None:
    """Validate the LLM chart spec against the result columns; build chart data."""
    if not isinstance(chart_spec, dict):
        return None
    ctype = str(chart_spec.get("type", "none")).lower()
    if ctype == "none":
        return None

    table = _build_table(summary)
    if not table:
        return None
    cols = table["columns"]
    x = chart_spec.get("x") or (cols[0] if cols else "")
    y = chart_spec.get("y") or (cols[1] if len(cols) > 1 else (cols[0] if cols else ""))
    if x not in cols or y not in cols:
        # Fall back to the first two columns of the aggregate.
        x = cols[0] if cols else ""
        y = cols[1] if len(cols) > 1 else x
    xi = cols.index(x) if x in cols else 0
    yi = cols.index(y) if y in cols else (1 if len(cols) > 1 else 0)

    data = [{"x": row[xi], "y": row[yi]} for row in table["rows"]]
    return {
        "type": ctype,
        "x_key": x,
        "y_key": y,
        "title": chart_spec.get("title") or "",
        "data": data,
    }
