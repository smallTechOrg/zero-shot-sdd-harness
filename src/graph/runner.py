"""Run entry point — the API's POST handler calls `start_design_run` blind.

Creates the run row, builds initial state (session history + prior params +
preset), registers the progress channel, launches the compiled graph in a
daemon thread, and returns the run_id immediately. The thread wrapper catches
ALL exceptions: a run can fail, but it can never stall silently.
"""

import threading
import time

from graph import persistence
from graph.agent import compiled_graph
from graph.state import AgentState
from graph.steps import initial_steps
from observability import progress
from observability.events import get_logger


def start_design_run(session_id: str, prompt: str, preset_id: str | None = None) -> str:
    run_id = persistence.create_run_row(session_id, prompt)
    state: AgentState = {
        "run_id": run_id,
        "session_id": session_id,
        "user_prompt": prompt,
        "messages": persistence.load_messages(session_id, exclude_run_id=run_id),
        "prior_params": persistence.load_prior_params(session_id, exclude_run_id=run_id),
        "preset_values": persistence.load_preset_values(preset_id),
        "in_scope": True,
        "scope_message": None,
        "plan_text": "",
        "params": None,
        "missing_critical": [],
        "warnings": [],
        "clarification_question": None,
        "geometry": None,
        "assumptions": [],
        "trail": [],
        "artefacts": [],
        "token_usage": [],
        "steps": initial_steps(),
        "started_monotonic": time.monotonic(),
        "status": "running",
        "error": None,
    }
    progress.register(run_id)
    threading.Thread(
        target=_run_graph,
        args=(state,),
        daemon=True,
        name=f"design-run-{run_id[:8]}",
    ).start()
    return run_id


def _run_graph(state: AgentState) -> None:
    run_id = state["run_id"]
    log = get_logger("agent.runner").bind(run_id=run_id, session_id=state["session_id"])
    log.info("run_started", prompt_chars=len(state["user_prompt"]))
    try:
        final = compiled_graph.invoke(state)
        log.info("run_finished", status=final.get("status"))
    except Exception as exc:  # catch-all: transparent failure, never a silent stall
        message = f"The design run crashed unexpectedly: {exc}"
        log.error("run_crashed", error=str(exc))
        try:
            persistence.finish_run(
                run_id,
                status="failed",
                error_message=message,
                steps=state.get("steps"),
                duration_ms=int(
                    (time.monotonic() - state["started_monotonic"]) * 1000
                ),
            )
        except Exception as persist_exc:
            log.error("failure_persistence_failed", error=str(persist_exc))
        finally:
            progress.publish(
                run_id, "error", {"code": "RUN_FAILED", "message": message}
            )
