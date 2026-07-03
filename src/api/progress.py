"""Progress endpoint: live step-by-step run progress as Server-Sent Events.

`GET /runs/{run_id}/progress` streams the graph's per-node progress events
("Planning… / Running code… / Retrying… / Writing answer…") as SSE frames. The
frontend typically opens this stream first, then fires `POST /runs`; the
ProgressBus lazily creates the run's queue so no events are lost.
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from observability.progress import progress_bus

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Disable proxy buffering so events flush immediately.
    "X-Accel-Buffering": "no",
}


@router.get("/runs/{run_id}/progress")
async def run_progress(run_id: str) -> StreamingResponse:
    async def event_gen():
        async for event in progress_bus.subscribe(run_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
