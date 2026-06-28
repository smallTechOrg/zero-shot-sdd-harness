"""In-process per-run event bus for the SSE stream.

The runner publishes node events (plan / step / retry / final / error) to a
thread-safe queue keyed by run_id; the SSE endpoint drains it. Single-user,
in-memory — no broker. A sentinel `None` marks the end of a stream.
"""
from __future__ import annotations

import queue
import threading

_STREAMS: dict[str, "queue.Queue"] = {}
_LOCK = threading.Lock()

# Sentinel pushed to signal the stream is finished.
DONE = object()


def open_stream(run_id: str) -> "queue.Queue":
    with _LOCK:
        q: queue.Queue = queue.Queue()
        _STREAMS[run_id] = q
        return q


def get_stream(run_id: str) -> "queue.Queue | None":
    with _LOCK:
        return _STREAMS.get(run_id)


def publish(run_id: str, event_type: str, payload: dict) -> None:
    q = get_stream(run_id)
    if q is not None:
        q.put({"type": event_type, "payload": payload})


def close_stream(run_id: str) -> None:
    q = get_stream(run_id)
    if q is not None:
        q.put(DONE)


def drop_stream(run_id: str) -> None:
    with _LOCK:
        _STREAMS.pop(run_id, None)
