"""run_agent — the agent entry point: build state from DB, run the graph, persist.

Loads dataset schema/sample + recent conversation turns from SQLite, ensures the dataset's
DuckDB tables are loaded, runs the ReAct graph, then writes the run + assistant message.
Provides a streaming variant that emits one `step` event per action_history append.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datachat.data import engine
from datachat.db.models import Conversation, File, Message, Run
from datachat.graph.agent import get_compiled_graph
from datachat.memory.context import summarize_schema
from datachat.observability.events import get_logger

RECENT_TURNS_LIMIT = 10


class DatasetNotLoadedError(RuntimeError):
    pass


async def _load_context(session: AsyncSession, conversation: Conversation) -> dict[str, Any]:
    files = (
        await session.execute(
            select(File).where(File.dataset_id == conversation.dataset_id)
        )
    ).scalars().all()
    if not files:
        raise DatasetNotLoadedError("This dataset has no uploaded files yet.")

    # The file-backed DuckDB persists across restarts; if its file is gone, report it.
    if not engine.has_connection(conversation.dataset_id):
        raise DatasetNotLoadedError(
            "Session data is no longer available — please re-upload the dataset's files."
        )

    file_dicts = [
        {
            "filename": f.filename,
            "duckdb_table": f.duckdb_table,
            "schema_json": f.schema_json,
            "sample_rows_json": f.sample_rows_json,
        }
        for f in files
    ]
    schema_summary, sample_rows = summarize_schema(file_dicts)

    rows = (
        await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(RECENT_TURNS_LIMIT)
        )
    ).scalars().all()
    recent_turns = [{"role": m.role, "content": m.content} for m in reversed(rows)]
    return {
        "schema_summary": schema_summary,
        "sample_rows": sample_rows,
        "recent_turns": recent_turns,
    }


async def _run_graph(initial: dict[str, Any]) -> dict[str, Any]:
    graph = get_compiled_graph()
    return await asyncio.to_thread(graph.invoke, initial)


_STREAM_DONE = object()


async def stream_agent(
    session: AsyncSession, conversation: Conversation, question: str
) -> AsyncIterator[dict[str, Any]]:
    """Run the agent and yield events as nodes execute, then persist + yield the final answer.

    Yields dicts: {"type": "step", "step": {...}} per new action_history entry, then
    {"type": "answer", "message": {...}} / {"type": "error", ...}, then {"type": "done", ...}.
    Streaming as work happens keeps bytes flowing so the client doesn't abort on a long run.
    """
    log = get_logger(conversation_id=conversation.id)

    run = Run(conversation_id=conversation.id, status="running")
    session.add(run)
    session.add(Message(conversation_id=conversation.id, role="user", content=question))
    await session.commit()
    await session.refresh(run)

    try:
        ctx = await _load_context(session, conversation)
    except DatasetNotLoadedError as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = datetime.utcnow()
        await session.commit()
        yield {"type": "error", "code": "DATASET_NOT_LOADED", "message": str(exc)}
        return

    initial: dict[str, Any] = {
        "run_id": run.id, "conversation_id": conversation.id,
        "dataset_id": conversation.dataset_id, "question": question,
        "action_history": [], "iteration_count": 0, "tokens_input": 0, "tokens_output": 0,
        **ctx,
    }

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def run_in_thread() -> None:
        graph = get_compiled_graph()
        emitted = 0
        final_state: dict[str, Any] = {}
        try:
            for state in graph.stream(initial, stream_mode="values"):
                final_state = state
                history = state.get("action_history", [])
                while emitted < len(history):
                    loop.call_soon_threadsafe(queue.put_nowait, {"type": "step", "step": history[emitted]})
                    emitted += 1
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "_final", "state": final_state})

    task = loop.run_in_executor(None, run_in_thread)

    final: dict[str, Any] = {}
    while True:
        item = await queue.get()
        if item.get("type") == "_final":
            final = item["state"]
            break
        yield item
    await task

    run.iteration_count = final.get("iteration_count", 0)
    run.tokens_input = final.get("tokens_input", 0)
    run.tokens_output = final.get("tokens_output", 0)
    run.estimated_cost_usd = final.get("estimated_cost_usd")
    run.early_exit_reason = final.get("early_exit_reason")
    run.completed_at = datetime.utcnow()

    if final.get("error"):
        run.status = "failed"
        run.error_message = final["error"]
        assistant = Message(
            conversation_id=conversation.id, run_id=run.id, role="assistant",
            content=f"Sorry — I couldn't answer this: {final['error']}",
        )
        session.add(assistant)
        await session.commit()
        log.error("run.failed", run_id=run.id, error=final["error"])
        yield {"type": "error", "code": "RUN_FAILED", "message": final["error"]}
        return

    run.status = "completed"
    assistant = Message(
        conversation_id=conversation.id, run_id=run.id, role="assistant",
        content=final.get("final_answer") or "Done.",
        result_table_json=final.get("result_table"),
        chart_json=final.get("chart"),
        trace_json=final.get("action_history"),
    )
    session.add(assistant)
    await session.commit()
    await session.refresh(assistant)
    log.info("run.persisted", run_id=run.id, status=run.status)

    yield {
        "type": "answer",
        "message": {
            "id": assistant.id, "conversation_id": assistant.conversation_id,
            "run_id": assistant.run_id, "role": "assistant", "content": assistant.content,
            "result_table": assistant.result_table_json, "chart": assistant.chart_json,
            "trace": assistant.trace_json, "created_at": assistant.created_at.isoformat(),
        },
    }
    yield {
        "type": "done",
        "run": {
            "run_id": run.id, "status": run.status, "tokens_input": run.tokens_input,
            "tokens_output": run.tokens_output, "estimated_cost_usd": run.estimated_cost_usd,
            "early_exit_reason": run.early_exit_reason,
        },
    }


async def run_agent(
    session: AsyncSession, conversation: Conversation, question: str
) -> tuple[Run, Message]:
    """Run one question→answer cycle; persist the run + user/assistant messages."""
    log = get_logger(conversation_id=conversation.id)

    run = Run(conversation_id=conversation.id, status="running")
    session.add(run)
    user_msg = Message(conversation_id=conversation.id, role="user", content=question)
    session.add(user_msg)
    await session.commit()
    await session.refresh(run)

    ctx = await _load_context(session, conversation)
    initial: dict[str, Any] = {
        "run_id": run.id,
        "conversation_id": conversation.id,
        "dataset_id": conversation.dataset_id,
        "question": question,
        "action_history": [],
        "iteration_count": 0,
        "tokens_input": 0,
        "tokens_output": 0,
        **ctx,
    }

    final = await _run_graph(initial)

    run.iteration_count = final.get("iteration_count", 0)
    run.tokens_input = final.get("tokens_input", 0)
    run.tokens_output = final.get("tokens_output", 0)
    run.estimated_cost_usd = final.get("estimated_cost_usd")
    run.early_exit_reason = final.get("early_exit_reason")
    run.completed_at = datetime.utcnow()

    if final.get("error"):
        run.status = "failed"
        run.error_message = final["error"]
        await session.commit()
        log.error("run.failed", run_id=run.id, error=final["error"])
        assistant = Message(
            conversation_id=conversation.id,
            run_id=run.id,
            role="assistant",
            content=f"Sorry — I couldn't answer this: {final['error']}",
        )
        session.add(assistant)
        await session.commit()
        await session.refresh(assistant)
        return run, assistant

    run.status = "completed"
    assistant = Message(
        conversation_id=conversation.id,
        run_id=run.id,
        role="assistant",
        content=final.get("final_answer") or "Done.",
        result_table_json=final.get("result_table"),
        chart_json=final.get("chart"),
        trace_json=final.get("action_history"),
    )
    session.add(assistant)
    await session.commit()
    await session.refresh(assistant)
    log.info("run.persisted", run_id=run.id, status=run.status)
    return run, assistant
