"""The ten pipeline nodes per spec/agent.md.

LLM nodes (understand, extract) orchestrate and narrate; every engineering
computation is deterministic. Phase 1: check / model3d / review are labelled
skip-stubs; analyse is the sizing subset; draw produces the real GA DXF + SVG.
Every node body is wrapped — exceptions set state["error"] and route to
handle_error (clarify/finalize/handle_error propagate to the runner's catch-all).
"""

import functools
import time
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from config.settings import get_settings
from domain.culvert import Assumption, BoxGeometry, CulvertParams, unusual_value_warnings
from engine import size_culvert
from graph import persistence
from graph.accounting import compute_cost_usd, run_totals
from graph.extraction import (
    ExtractionResult,
    merge_params,
    select_clarification,
    validation_error_message,
)
from graph.state import AgentState
from graph.steps import StepTracker, duration_ms
from llm.client import LLMClient, LLMResult
from observability.events import get_logger
from observability.progress import publish

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

_ARTIFACT_MIME = {"ga_dxf": "image/vnd.dxf", "ga_svg": "image/svg+xml"}
_ARTIFACT_ORDER = ("ga_dxf", "ga_svg")


class UnderstandResult(BaseModel):
    """Structured output of the scope gate + plan (understand.md)."""

    in_scope: bool = Field(
        description="True only for designing/refining a single-cell RCC box culvert "
        "or answering a pending clarification about one."
    )
    scope_message: str | None = Field(
        default=None,
        description="Graceful one-paragraph scope statement — set ONLY when in_scope is false.",
    )
    plan: str = Field(
        default="",
        description="Plain-language design plan (2–4 short sentences) — set ONLY when in_scope is true.",
    )


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8").strip()


def _log(state: AgentState, node: str):
    return get_logger("agent.graph").bind(run_id=state.get("run_id"), node=node)


def _node(fn):
    """Log node enter/exit with duration — one structlog line each way."""

    @functools.wraps(fn)
    def wrapper(state: AgentState) -> dict:
        log = _log(state, fn.__name__)
        log.info("node_entered")
        started = time.monotonic()
        updates = fn(state)
        log.info(
            "node_exited",
            node_ms=int((time.monotonic() - started) * 1000),
            error=updates.get("error"),
        )
        return updates

    return wrapper


def _conversation(state: AgentState) -> str:
    """The extraction/scoping context: prior turns + this turn's request."""
    lines: list[str] = []
    messages = state.get("messages") or []
    if messages:
        lines.append("Conversation so far:")
        lines.extend(f"{m['role']}: {m['content']}" for m in messages)
        lines.append("")
    lines.append(f"Current request: {state['user_prompt']}")
    return "\n".join(lines)


def _record_llm_call(state: AgentState, node: str, result: LLMResult) -> list[dict]:
    """Append usage to state, publish the running `tokens` event, log the call."""
    token_usage = list(state.get("token_usage") or []) + [
        {
            "node": node,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "latency_ms": result.latency_ms,
        }
    ]
    prompt_tokens, completion_tokens = run_totals(token_usage)
    cost_usd = compute_cost_usd(prompt_tokens, completion_tokens)
    session_total = persistence.session_cost_sum(state["session_id"]) + cost_usd
    publish(
        state["run_id"],
        "tokens",
        {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": round(cost_usd, 6),
            "session_total_cost_usd": round(session_total, 6),
        },
    )
    _log(state, node).info(
        "llm_call",
        model=get_settings().llm_model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        latency_ms=result.latency_ms,
    )
    return token_usage


def _narrate(state: AgentState, text: str) -> None:
    publish(state["run_id"], "narration", {"text": text})


# --------------------------------------------------------------------------- nodes


@_node
def understand(state: AgentState) -> dict:
    tracker = StepTracker(state)
    tracker.mark("Understand", "active", detail="Reading the request")
    try:
        result = LLMClient().generate(
            _conversation(state),
            system=_load_prompt("understand.md"),
            schema=UnderstandResult,
            temperature=0.2,
        )
        token_usage = _record_llm_call(state, "understand", result)
        parsed: UnderstandResult = result.parsed
        if not parsed.in_scope:
            scope_message = parsed.scope_message or (
                "This demonstrator designs and proof-checks single-cell RCC box "
                "culverts to IRS codes — that request is outside its scope."
            )
            _narrate(state, scope_message)
            tracker.mark("Understand", "done", detail="Out of scope")
            return {
                "in_scope": False,
                "scope_message": scope_message,
                "plan_text": "",
                "token_usage": token_usage,
                "steps": tracker.steps,
            }
        _narrate(state, parsed.plan)
        tracker.mark("Understand", "done")
        return {
            "in_scope": True,
            "scope_message": None,
            "plan_text": parsed.plan,
            "token_usage": token_usage,
            "steps": tracker.steps,
        }
    except Exception as exc:
        tracker.mark("Understand", "failed", detail=str(exc))
        return {
            "steps": tracker.steps,
            "error": f"Understanding the request failed (Gemini scope gate): {exc}",
        }


@_node
def extract(state: AgentState) -> dict:
    tracker = StepTracker(state)
    tracker.mark("Extract", "active", detail="Extracting design parameters")
    try:
        result = LLMClient().generate(
            _conversation(state),
            system=_load_prompt("extract.md"),
            schema=ExtractionResult,
            temperature=0.0,
        )
        token_usage = _record_llm_call(state, "extract", result)
        extracted = {k: v for k, v in result.parsed.model_dump().items() if v is not None}
        outcome = merge_params(
            extracted, state.get("prior_params"), state.get("preset_values") or {}
        )
        if outcome.missing_critical:
            # Clarify (still the Extract UI step) publishes the question and closes the run.
            return {
                "params": None,
                "missing_critical": outcome.missing_critical,
                "token_usage": token_usage,
                "steps": tracker.steps,
            }
        try:
            params = CulvertParams(**outcome.merged)
        except ValidationError as exc:
            message = validation_error_message(exc)
            tracker.mark("Extract", "failed", detail=message)
            return {
                "token_usage": token_usage,
                "steps": tracker.steps,
                "error": f"Parameter validation failed: {message}",
            }
        warnings = unusual_value_warnings(params)
        for warning in warnings:
            publish(state["run_id"], "warning", {"message": warning})
        preset_assumptions = [
            Assumption(
                field=field,
                value=outcome.merged[field],
                source="preset",
                note="Applied from the defaults preset — not stated by the user.",
            ).model_dump()
            for field in outcome.preset_fields
        ]
        tracker.mark(
            "Extract",
            "done",
            detail=(
                f"{params.clear_span_m:g} × {params.clear_height_m:g} m box, "
                f"cushion {params.cushion_m:g} m"
            ),
        )
        return {
            "params": params.model_dump(mode="json"),
            "missing_critical": [],
            "warnings": list(state.get("warnings") or []) + warnings,
            "assumptions": list(state.get("assumptions") or []) + preset_assumptions,
            "token_usage": token_usage,
            "steps": tracker.steps,
        }
    except Exception as exc:
        tracker.mark("Extract", "failed", detail=str(exc))
        return {
            "steps": tracker.steps,
            "error": f"Parameter extraction failed (Gemini structured output): {exc}",
        }


@_node
def clarify(state: AgentState) -> dict:
    """Deterministic: ONE pointed question, run ends at needs_input (terminal)."""
    tracker = StepTracker(state)
    field, question = select_clarification(state["missing_critical"])
    publish(
        state["run_id"], "clarification", {"question": question, "missing_param": field}
    )
    tracker.mark("Extract", "done", detail=f"Needs input — asked for {field}")

    prompt_tokens, completion_tokens = run_totals(state.get("token_usage") or [])
    cost_usd = compute_cost_usd(prompt_tokens, completion_tokens)
    persistence.finish_run(
        state["run_id"],
        status="needs_input",
        clarification_question=question,
        plan_text=state.get("plan_text"),
        steps=tracker.steps,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
        duration_ms=duration_ms(state),
    )
    publish(
        state["run_id"],
        "tokens",
        {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": round(cost_usd, 6),
            "session_total_cost_usd": round(
                persistence.session_cost_sum(state["session_id"]), 6
            ),
        },
    )
    publish(state["run_id"], "done", {"status": "needs_input", "verdict": None})
    _log(state, "clarify").info("run_outcome", status="needs_input", missing_param=field)
    return {
        "status": "needs_input",
        "clarification_question": question,
        "steps": tracker.steps,
    }


@_node
def analyse(state: AgentState) -> dict:
    tracker = StepTracker(state)
    tracker.mark("Analyse", "active", detail="Running the IRS sizing engine")
    try:
        params = CulvertParams(**state["params"])
        _narrate(state, f"Sizing members for {params.clear_span_m:g} m span…")
        result = size_culvert(params)
        for warning in result.warnings:
            publish(state["run_id"], "warning", {"message": warning})
        geometry = result.geometry
        tracker.mark(
            "Analyse",
            "done",
            detail=(
                f"Top slab {geometry.top_slab_thickness_mm:g} mm, walls "
                f"{geometry.wall_thickness_mm:g} mm, barrel {geometry.barrel_length_m:g} m"
            ),
        )
        return {
            "geometry": geometry.model_dump(),
            "assumptions": list(state.get("assumptions") or [])
            + [a.model_dump() for a in result.assumptions],
            "trail": [step.model_dump() for step in result.trail],
            "warnings": list(state.get("warnings") or []) + result.warnings,
            "steps": tracker.steps,
        }
    except Exception as exc:
        tracker.mark("Analyse", "failed", detail=str(exc))
        return {"steps": tracker.steps, "error": f"Sizing the culvert failed: {exc}"}


@_node
def check(state: AgentState) -> dict:
    """Phase-1 labelled skip-stub — IRS CBC member checks land in Phase 2."""
    tracker = StepTracker(state)
    tracker.mark("Check", "skipped", detail="Coming in Phase 2")
    return {"steps": tracker.steps}


@_node
def draw(state: AgentState) -> dict:
    tracker = StepTracker(state)
    tracker.mark("Draw", "active", detail="Drawing the GA sheet")
    try:
        from drawing.ga import generate_ga  # deterministic sibling slice — pinned contract

        run_id = state["run_id"]
        geometry = BoxGeometry(**state["geometry"])
        params = CulvertParams(**state["params"])
        out_dir = Path(get_settings().artifacts_dir) / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        _narrate(state, "Drawing the GA sheet — plan, sections, dimensions…")

        paths = generate_ga(geometry, params, out_dir, run_id=run_id)

        artefacts = list(state.get("artefacts") or [])
        for kind in _ARTIFACT_ORDER:
            path = paths[kind]
            size_bytes = path.stat().st_size
            persistence.record_artifact(
                run_id, kind, path.name, _ARTIFACT_MIME[kind], size_bytes
            )
            publish(
                run_id,
                "artefact",
                {
                    "kind": kind,
                    "filename": path.name,
                    "url": f"/api/designs/{run_id}/artifacts/{path.name}",
                },
            )
            artefacts.append({"kind": kind, "filename": path.name})
            _log(state, "draw").info(
                "artefact_written", kind=kind, filename=path.name, size_bytes=size_bytes
            )
        tracker.mark("Draw", "done", detail="GA drawing ready (DXF + SVG)")
        return {"artefacts": artefacts, "steps": tracker.steps}
    except Exception as exc:
        tracker.mark("Draw", "failed", detail=str(exc))
        return {"steps": tracker.steps, "error": f"GA drawing generation failed: {exc}"}


@_node
def model3d(state: AgentState) -> dict:
    """Phases 1–2 labelled skip-stub (3D lives inside the Draw UI step) — non-fatal by design."""
    tracker = StepTracker(state)
    try:
        tracker.mark("Draw", "skipped", detail="3D model — coming in Phase 3")
    except Exception as exc:  # never fatal per spec/agent.md
        publish(state["run_id"], "warning", {"message": f"3D model step degraded: {exc}"})
        _log(state, "model3d").warning("model3d_degraded", error=str(exc))
    return {"steps": tracker.steps}


@_node
def review(state: AgentState) -> dict:
    """Phase-1 labelled skip-stub — the automatic proof-check lands in Phase 2."""
    tracker = StepTracker(state)
    tracker.mark("Review", "skipped", detail="Coming in Phase 2")
    return {"steps": tracker.steps}


@_node
def finalize(state: AgentState) -> dict:
    status = "completed" if state.get("in_scope", True) else "out_of_scope"
    prompt_tokens, completion_tokens = run_totals(state.get("token_usage") or [])
    cost_usd = compute_cost_usd(prompt_tokens, completion_tokens)
    persistence.finish_run(
        state["run_id"],
        status=status,
        plan_text=state.get("plan_text") or None,
        scope_message=state.get("scope_message"),
        params=state.get("params"),
        assumptions=state.get("assumptions"),
        warnings=state.get("warnings"),
        steps=state.get("steps"),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
        duration_ms=duration_ms(state),
    )
    publish(
        state["run_id"],
        "tokens",
        {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": round(cost_usd, 6),
            "session_total_cost_usd": round(
                persistence.session_cost_sum(state["session_id"]), 6
            ),
        },
    )
    publish(state["run_id"], "done", {"status": status, "verdict": None})
    _log(state, "finalize").info(
        "run_outcome",
        status=status,
        duration_ms=duration_ms(state),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=round(cost_usd, 6),
    )
    return {"status": status}


@_node
def handle_error(state: AgentState) -> dict:
    error = state.get("error") or "Unknown failure — no error detail was recorded."
    prompt_tokens, completion_tokens = run_totals(state.get("token_usage") or [])
    cost_usd = compute_cost_usd(prompt_tokens, completion_tokens)
    persistence.finish_run(
        state["run_id"],
        status="failed",
        error_message=error,
        plan_text=state.get("plan_text") or None,
        steps=state.get("steps"),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
        duration_ms=duration_ms(state),
    )
    publish(state["run_id"], "error", {"code": "RUN_FAILED", "message": error})
    _log(state, "handle_error").error(
        "run_outcome", status="failed", error=error, duration_ms=duration_ms(state)
    )
    return {"status": "failed"}
