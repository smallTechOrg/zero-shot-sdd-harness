"""In-process progress bus for live step-by-step run progress over SSE.

`publish`/`finish` are called from the SYNCHRONOUS graph worker (running in the
request thread), while `subscribe` is consumed by the async event loop serving
the SSE endpoint. Because these cross a thread boundary, each run's events go
through a stdlib `queue.Queue` (thread-safe) rather than an asyncio.Queue. The
async subscriber polls the queue with `get_nowait()` and sleeps briefly on empty.

The bus tolerates `subscribe` being called BEFORE the first `publish` — the
frontend opens the SSE connection first, then fires `POST /runs`. The per-run
queue is created lazily on whichever of subscribe/publish happens first.
"""
from __future__ import annotations

import asyncio
import queue
import threading

from observability.events import get_logger

_log = get_logger("observability.progress")

# Overall cap so a stuck/never-finished run can't hold the SSE connection open
# forever. Generous — a typical run is seconds; retries add a little.
_SUBSCRIBE_TIMEOUT_SECONDS = 180.0
_POLL_INTERVAL_SECONDS = 0.05


class ProgressBus:
    def __init__(self) -> None:
        self._queues: dict[str, queue.Queue] = {}
        self._lock = threading.Lock()

    def _get_queue(self, run_id: str) -> queue.Queue:
        """Return the run's queue, creating it lazily under the lock."""
        with self._lock:
            q = self._queues.get(run_id)
            if q is None:
                q = queue.Queue()
                self._queues[run_id] = q
            return q

    def publish(self, run_id: str, step: str, detail: str = "") -> None:
        """Emit one progress event for a run (called from the sync worker)."""
        self._get_queue(run_id).put({"step": step, "detail": detail})

    def finish(self, run_id: str, status: str = "completed") -> None:
        """Emit the terminal sentinel for a run; the subscriber stops after it."""
        self._get_queue(run_id).put({"step": "done", "status": status})

    async def subscribe(self, run_id: str):
        """Async generator yielding this run's events until the terminal one.

        Yields each `{"step", ...}` event in order. Stops after yielding the
        terminal `{"step": "done", ...}` event, or when the overall timeout is
        exceeded. Cleans up the run's queue on exit.
        """
        q = self._get_queue(run_id)
        loop = asyncio.get_event_loop()
        deadline = loop.time() + _SUBSCRIBE_TIMEOUT_SECONDS
        try:
            while True:
                if loop.time() > deadline:
                    _log.warning("progress.subscribe_timeout", run_id=run_id)
                    yield {"step": "done", "status": "timeout"}
                    return
                try:
                    event = q.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(_POLL_INTERVAL_SECONDS)
                    continue
                yield event
                if event.get("step") == "done":
                    return
        finally:
            with self._lock:
                self._queues.pop(run_id, None)


# Module-level singleton — the graph nodes publish to it, the SSE endpoint
# subscribes to it.
progress_bus = ProgressBus()
