"""Conversation routes — start, multi-turn query (SSE), history."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from datachat.api._common import api_error, ok
from datachat.db.models import Conversation, Dataset, Message, Run
from datachat.db.session import get_session, get_sessionmaker
from datachat.domain import ConversationCreate, QueryRequest
from datachat.graph.runner import stream_agent

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _message_dict(m: Message) -> dict:
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "run_id": m.run_id,
        "role": m.role,
        "content": m.content,
        "result_table": m.result_table_json,
        "chart": m.chart_json,
        "trace": m.trace_json,
        "created_at": m.created_at.isoformat(),
    }


@router.post("")
async def create_conversation(body: ConversationCreate, session: AsyncSession = Depends(get_session)):
    ds = await session.get(Dataset, body.dataset_id)
    if ds is None:
        raise api_error("NOT_FOUND", "Dataset not found.", status=404)
    conv = Conversation(dataset_id=body.dataset_id, title=body.title)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return ok(
        {"id": conv.id, "dataset_id": conv.dataset_id, "title": conv.title,
         "created_at": conv.created_at.isoformat()},
        status=201,
    )


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str, session: AsyncSession = Depends(get_session)):
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise api_error("NOT_FOUND", "Conversation not found.", status=404)
    rows = (
        await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
    ).scalars().all()
    return ok(
        {"id": conv.id, "dataset_id": conv.dataset_id, "title": conv.title,
         "created_at": conv.created_at.isoformat(),
         "messages": [_message_dict(m) for m in rows]}
    )


async def _has_active_run(session: AsyncSession, conversation_id: str) -> bool:
    row = (
        await session.execute(
            select(Run).where(Run.conversation_id == conversation_id, Run.status == "running")
        )
    ).first()
    return row is not None


@router.post("/{conversation_id}/query")
async def query(
    conversation_id: str,
    body: QueryRequest,
    session: AsyncSession = Depends(get_session),
):
    """Run a question and stream the live agent trace + final answer over SSE."""
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise api_error("NOT_FOUND", "Conversation not found.", status=404)
    if await _has_active_run(session, conversation_id):
        raise api_error("RUN_IN_PROGRESS", "A query is already running on this conversation.", status=409)

    question = body.question.strip()
    if not question:
        raise api_error("EMPTY_QUESTION", "The question is empty.", status=422)

    async def event_stream():
        # Use a fresh session for the run so it isn't tied to the request's dependency scope.
        async with get_sessionmaker()() as run_session:
            conversation = await run_session.get(Conversation, conversation_id)
            async for ev in stream_agent(run_session, conversation, question):
                kind = ev["type"]
                if kind == "step":
                    yield {"event": "step", "data": json.dumps(ev["step"])}
                elif kind == "answer":
                    yield {"event": "answer", "data": json.dumps(ev["message"])}
                elif kind == "done":
                    yield {"event": "done", "data": json.dumps(ev["run"])}
                elif kind == "error":
                    yield {"event": "error",
                           "data": json.dumps({"code": ev["code"], "message": ev["message"]})}

    return EventSourceResponse(event_stream())
