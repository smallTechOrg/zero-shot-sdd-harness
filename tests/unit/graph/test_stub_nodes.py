"""model3d — the one remaining labelled skip-stub (Phases 1–2); never downgrades Draw."""

import time
from uuid import uuid4

from graph.nodes import model3d
from graph.steps import initial_steps
from observability import progress


def _state() -> dict:
    return {
        "run_id": f"test-{uuid4()}",
        "started_monotonic": time.monotonic(),
        "steps": initial_steps(),
    }


def _events(run_id: str) -> list[dict]:
    progress.publish(run_id, "done", {"status": "completed", "verdict": None})
    return list(progress.stream(run_id))


def test_model3d_publishes_draw_skipped_but_keeps_draw_done():
    """3D lives inside the Draw UI step; the real 2D drawing must stay 'done'."""
    state = _state()
    for s in state["steps"]:
        if s["name"] == "Draw":
            s["status"] = "done"
    progress.register(state["run_id"])

    updates = model3d(state)

    entry = next(s for s in updates["steps"] if s["name"] == "Draw")
    assert entry["status"] == "done"
    step_events = [e for e in _events(state["run_id"]) if e["event"] == "step"]
    assert step_events[0]["data"]["step"] == "Draw"
    assert step_events[0]["data"]["status"] == "skipped"
    assert "Phase 3" in step_events[0]["data"]["detail"]
