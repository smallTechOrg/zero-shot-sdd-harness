"""Plan-then-execute graph nodes.

Privacy invariant: only `schema`, `sample_rows`, prior bounded `steps[].result`,
and `question_text` are ever placed into an LLM prompt. No node reads the full
CSV into a prompt — the full data is touched only by the local AnalysisEngine.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from analysis.engine import AnalysisEngine, EngineError
from config.settings import get_settings
from graph.state import AgentState
from llm.client import LLMClient
from observability.events import get_logger

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
_log = get_logger("graph")


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8").strip()


def _parse_json(text: str) -> dict:
    """Parse a JSON object out of an LLM response, tolerating code fences/prose."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start = t.find("{")
        end = t.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(t[start : end + 1])
        raise


def _context_block(state: AgentState) -> str:
    """Build the privacy-bounded context sent to the LLM: schema + sample rows."""
    schema = state.get("schema", [])
    sample = state.get("sample_rows", [])
    return (
        f"QUESTION:\n{state.get('question_text', '')}\n\n"
        f"COLUMN SCHEMA:\n{json.dumps(schema)}\n\n"
        f"SAMPLE ROWS (a small slice only — the full data is local):\n"
        f"{json.dumps(sample)}\n"
    )


def _prior_results_block(state: AgentState) -> str:
    safe_steps = [
        {
            "index": s.get("index"),
            "language": s.get("language"),
            "code": s.get("code"),
            "result": s.get("result"),
            "error": s.get("error"),
        }
        for s in state.get("steps", [])
    ]
    return f"PLAN:\n{json.dumps(state.get('plan', []))}\n\nPRIOR STEP RESULTS (bounded aggregates):\n{json.dumps(safe_steps)}\n"


def _add_tokens(state: AgentState, ti: int, to: int) -> tuple[int, int]:
    return state.get("tokens_in", 0) + ti, state.get("tokens_out", 0) + to


# --- nodes -----------------------------------------------------------------

def plan(state: AgentState) -> AgentState:
    try:
        settings = get_settings()
        system = _load_prompt("plan.md").replace("{max_steps}", str(settings.max_steps))
        prompt = _context_block(state)
        text, ti, to = LLMClient().call_model_with_usage(prompt, system=system)
        parsed = _parse_json(text)

        plan_steps = parsed.get("plan") or ["Answer the question with a single aggregate query."]
        tokens_in, tokens_out = _add_tokens(state, ti, to)
        _log.info(
            "plan_produced",
            question_id=state.get("question_id"),
            plan_steps=len(plan_steps),
            tokens_in=ti,
            tokens_out=to,
        )
        return {
            **state,
            "plan": plan_steps,
            "next_code": parsed.get("code"),
            "next_language": parsed.get("language", "sql"),
            "plan_complete": len(plan_steps) <= 1,
            "step_count": 0,
            "steps": [],
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
    except Exception as exc:  # noqa: BLE001
        _log.error("plan_error", question_id=state.get("question_id"), error=str(exc))
        return {**state, "error": str(exc)}


def execute_step(state: AgentState) -> AgentState:
    settings = get_settings()
    code = state.get("next_code")
    language = state.get("next_language", "sql")
    index = state.get("step_count", 0)
    steps = list(state.get("steps", []))

    start = time.perf_counter()
    result_payload = None
    error = None
    if not code:
        error = "No code produced for this step."
    else:
        try:
            engine = AnalysisEngine(state["csv_path"], max_result_rows=settings.max_result_rows)
            res = engine.run(code, language=language)
            result_payload = res.as_dict()
        except EngineError as exc:
            error = str(exc)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
    latency_ms = int((time.perf_counter() - start) * 1000)

    row_count = len(result_payload["rows"]) if result_payload else 0
    _log.info(
        "execute_step",
        question_id=state.get("question_id"),
        step_index=index,
        language=language,
        code_hash=hash(code or ""),
        result_rows=row_count,
        latency_ms=latency_ms,
        error=error,
    )

    steps.append(
        {
            "index": index,
            "code": code or "",
            "language": language,
            "result": result_payload,
            "error": error,
            "latency_ms": latency_ms,
        }
    )
    return {
        **state,
        "steps": steps,
        "step_count": index + 1,
        "next_code": None,
    }


def replan(state: AgentState) -> AgentState:
    # Phase 1: minimal but real. If the plan is already complete (single-step
    # plans set this in `plan`), finish. Otherwise ask the LLM for the next step.
    if state.get("plan_complete"):
        return {**state, "plan_complete": True}
    try:
        system = _load_prompt("execute.md")
        prompt = _context_block(state) + "\n" + _prior_results_block(state)
        text, ti, to = LLMClient().call_model_with_usage(prompt, system=system)
        parsed = _parse_json(text)
        tokens_in, tokens_out = _add_tokens(state, ti, to)

        if parsed.get("plan_complete"):
            return {
                **state,
                "plan_complete": True,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            }
        return {
            **state,
            "plan_complete": False,
            "next_code": parsed.get("code"),
            "next_language": parsed.get("language", "sql"),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
    except Exception as exc:  # noqa: BLE001
        _log.error("replan_error", question_id=state.get("question_id"), error=str(exc))
        return {**state, "error": str(exc)}


def synthesize_answer(state: AgentState) -> AgentState:
    from graph.edges import cap_hit

    warning = state.get("cost_guard_warning")
    if not warning and cap_hit(state):
        warning = (
            f"Hit the step limit of {get_settings().max_steps} — "
            "returning the best answer so far."
        )

    try:
        system = _load_prompt("synthesize.md")
        prompt = (
            f"QUESTION:\n{state.get('question_text', '')}\n\n"
            + _prior_results_block(state)
        )
        if warning:
            prompt += f"\nNOTE: {warning}\n"
        text, ti, to = LLMClient().call_model_with_usage(prompt, system=system)
        parsed = _parse_json(text)
        tokens_in, tokens_out = _add_tokens(state, ti, to)

        _log.info(
            "answer_synthesized",
            question_id=state.get("question_id"),
            tokens_in=ti,
            tokens_out=to,
        )
        return {
            **state,
            "answer": parsed.get("answer", ""),
            "key_numbers": parsed.get("key_numbers", []),
            "result_table": parsed.get("result_table", {"columns": [], "rows": []}),
            "cost_guard_warning": warning,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
    except Exception as exc:  # noqa: BLE001
        _log.error("synthesize_error", question_id=state.get("question_id"), error=str(exc))
        return {**state, "error": str(exc), "cost_guard_warning": warning}


def suggest_followups(state: AgentState) -> AgentState:
    # Phase 1: passthrough — follow-ups become real in Phase 2.
    return {**state, "followups": state.get("followups", [])}


def handle_error(state: AgentState) -> AgentState:
    _log.error("run_failed", question_id=state.get("question_id"), error=state.get("error"))
    return {**state, "status": "failed"}


def finalize(state: AgentState) -> AgentState:
    return {**state, "status": "completed"}
