"""Phase 2 — cost & progress slice integration tests.

Real Gemini via .env (keys loaded through the provider). Covers:
  * happy path: a completed run records positive tokens_used + a cost estimate,
    proving the LLMClient accumulation → runner rollup path works end-to-end.
  * POST /cost/estimate returns a well-formed estimate + a boolean warn.
  * error path: unknown dataset → 404 from /cost/estimate.
  * expensive-run warning: lowering the threshold flips warn to True.
  * ProgressBus in isolation: ordered events + terminal sentinel (no live server).
"""
from __future__ import annotations

import asyncio
import io
import threading

import pytest

pytestmark = pytest.mark.usefixtures("_require_llm_key")


def _run_async(make_coro):
    """Run an async coroutine on a fresh event loop in a dedicated thread.

    The whole-tree run keeps a live event loop in the main thread (the
    pytest-playwright e2e suite), which makes both ``asyncio.run()`` and
    pytest-asyncio's per-test Runner raise "cannot be called from a running
    event loop". Driving the coroutine on its own loop in a separate thread is
    fully isolated from whatever the main thread is doing.

    ``make_coro`` is a zero-arg callable returning a fresh coroutine, so the
    coroutine is created inside the worker thread's loop context.
    """
    box: dict = {}

    def _worker() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            box["result"] = loop.run_until_complete(make_coro())
        except BaseException as exc:  # noqa: BLE001 — re-raised on the caller thread
            box["error"] = exc
        finally:
            loop.close()

    t = threading.Thread(target=_worker)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]
    return box["result"]


_CSV = (
    "region,amount\n"
    "North,100\n"
    "South,200\n"
    "North,150\n"
    "West,50\n"
    "South,300\n"
)

_QUESTION = "What is the total amount by region?"


def _upload_dataset(api_client) -> str:
    resp = api_client.post(
        "/datasets",
        files={"file": ("sales.csv", io.BytesIO(_CSV.encode()), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["error"] is None
    return body["data"]["id"]


def test_completed_run_records_tokens_and_cost(api_client):
    """Happy path — a real run rolls token usage + a dollar estimate up to the run."""
    dataset_id = _upload_dataset(api_client)

    resp = api_client.post("/runs", json={"dataset_id": dataset_id, "question": _QUESTION})
    assert resp.status_code == 200, resp.text
    run = resp.json()["data"]
    assert run["status"] == "completed", run
    run_id = run["run_id"]

    # Re-fetch to read the persisted accounting fields.
    got = api_client.get(f"/runs/{run_id}")
    assert got.status_code == 200, got.text
    data = got.json()["data"]

    assert isinstance(data["tokens_used"], int)
    assert data["tokens_used"] > 0, data
    assert data["cost_estimate_usd"] is not None
    assert float(data["cost_estimate_usd"]) >= 0.0


def test_cost_estimate_shape_and_warn_bool(api_client):
    """POST /cost/estimate returns a labelled estimate with a boolean warn flag."""
    dataset_id = _upload_dataset(api_client)

    resp = api_client.post(
        "/cost/estimate", json={"dataset_id": dataset_id, "question": _QUESTION}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["estimated_tokens"] > 0
    assert data["estimated_input_tokens"] > 0
    assert data["estimated_output_tokens"] > 0
    assert float(data["estimated_usd"]) >= 0.0
    assert isinstance(data["warn"], bool)
    assert "threshold_usd" in data


def test_cost_estimate_unknown_dataset_404(api_client):
    """Error path — unknown dataset id is a clean 404, not a 500."""
    resp = api_client.post(
        "/cost/estimate",
        json={"dataset_id": "does-not-exist", "question": _QUESTION},
    )
    assert resp.status_code == 404, resp.text


def test_cost_estimate_warns_when_threshold_lowered(api_client, monkeypatch):
    """Lowering the warn threshold flips warn to True for the same question."""
    dataset_id = _upload_dataset(api_client)

    # Default threshold ($0.05) is well above a single question's cost — no warn.
    baseline = api_client.post(
        "/cost/estimate", json={"dataset_id": dataset_id, "question": _QUESTION}
    ).json()["data"]
    assert baseline["warn"] is False

    # Drop the threshold to 0 and rebuild the settings singleton so the endpoint
    # (which reads the threshold live) now warns.
    monkeypatch.setenv("AGENT_COST_WARN_THRESHOLD_USD", "0")
    import config.settings as settings_module
    settings_module._settings = None

    warned = api_client.post(
        "/cost/estimate", json={"dataset_id": dataset_id, "question": _QUESTION}
    ).json()["data"]
    assert warned["warn"] is True
    assert warned["threshold_usd"] == 0.0


def test_progress_bus_orders_events_and_terminates():
    """ProgressBus (isolated) — events arrive in order and stop after the sentinel."""
    from observability.progress import ProgressBus

    bus = ProgressBus()
    run_id = "run-xyz"

    bus.publish(run_id, "planning", "Planning…")
    bus.publish(run_id, "running_code", "Running code…")
    bus.publish(run_id, "writing_answer", "Writing answer…")
    bus.finish(run_id, status="completed")

    async def _collect():
        events = []
        async for event in bus.subscribe(run_id):
            events.append(event)
        return events

    events = _run_async(_collect)

    assert [e["step"] for e in events] == [
        "planning",
        "running_code",
        "writing_answer",
        "done",
    ]
    assert events[-1]["status"] == "completed"


def test_progress_bus_subscribe_before_publish():
    """Subscribe may be opened before the first publish (frontend opens SSE first)."""
    from observability.progress import ProgressBus

    bus = ProgressBus()
    run_id = "run-early"

    async def _run():
        agen = bus.subscribe(run_id)
        # Publish AFTER the subscriber's generator exists — the per-run queue is
        # created lazily by whichever of subscribe/publish touches it first, so
        # no events are lost.
        bus.publish(run_id, "planning", "Planning…")
        bus.finish(run_id)
        collected = []
        async for event in agen:
            collected.append(event)
        return collected

    events = _run_async(_run)
    assert [e["step"] for e in events] == ["planning", "done"]
