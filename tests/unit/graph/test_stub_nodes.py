"""Phase-1 skip-stub nodes (check / model3d / review) — labelled, no fake work."""

import time
from uuid import uuid4

from graph.nodes import check, model3d, review
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


def test_check_marks_check_skipped_coming_in_phase_2():
    state = _state()
    progress.register(state["run_id"])

    updates = check(state)

    entry = next(s for s in updates["steps"] if s["name"] == "Check")
    assert entry["status"] == "skipped"
    assert entry["detail"] == "Coming in Phase 2"
    step_events = [e for e in _events(state["run_id"]) if e["event"] == "step"]
    assert step_events[0]["data"] == {
        "step": "Check",
        "status": "skipped",
        "detail": "Coming in Phase 2",
        "elapsed_ms": step_events[0]["data"]["elapsed_ms"],
    }
    assert "error" not in updates or updates.get("error") is None


def test_review_marks_review_skipped_coming_in_phase_2():
    state = _state()
    progress.register(state["run_id"])

    updates = review(state)

    entry = next(s for s in updates["steps"] if s["name"] == "Review")
    assert entry["status"] == "skipped"
    assert entry["detail"] == "Coming in Phase 2"


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
