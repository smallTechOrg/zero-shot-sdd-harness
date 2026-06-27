"""Session routes (Phase 3) — `/sessions` CRUD + `/datasets/{id}/sessions`.

A *session* is a multi-turn conversation scoped to one or more datasets. Each
turn is a `query_runs` row tagged with the session id. This router exposes the
session list (most-recently-updated first, with a turn summary), the session
detail (the full ordered list of turns, each rendered to HTML), rename, and
delete (one / all). It also serves the dataset-scoped session list — that route
lives here (not in `datasets.py`) to keep file ownership disjoint; FastAPI lets
any router register any path prefix.

All responses use the shared `ok()` / `api_error()` envelope.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from markdown_it import MarkdownIt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import ConversationSessionRow, DatasetRow, QueryRunRow
from db.session import get_session
from domain.session import SessionRenameRequest

router = APIRouter()

_md = MarkdownIt()

# A turn is a real run that produced an answer, a force-finalized best effort, a
# failure, or a clarification short-circuit. Pending/running rows are in-flight
# and not yet a settled turn.
_TURN_STATUSES = ("completed", "failed", "clarification")


def _session_datasets(row: ConversationSessionRow) -> list[str]:
    """The full dataset-id list for a session (json list, else the single id)."""
    if row.dataset_ids_json:
        return [d for d in row.dataset_ids_json if d]
    if row.dataset_id:
        return [row.dataset_id]
    return []


def _turn_runs(session: Session, session_id: str) -> list[QueryRunRow]:
    """All settled turn rows for a session, oldest-first."""
    return (
        session.execute(
            select(QueryRunRow)
            .where(QueryRunRow.session_id == session_id)
            .where(QueryRunRow.status.in_(_TURN_STATUSES))
            .order_by(QueryRunRow.created_at.asc())
        )
        .scalars()
        .all()
    )


def _turn_payload(run: QueryRunRow) -> dict:
    """Render one `query_runs` row into the turn shape the UI consumes."""
    is_clarification = run.status == "clarification"
    answer_markdown = run.answer or ""
    # For a clarification turn the `answer` field carries the clarifying question;
    # there is no rendered analysis answer, so answer_html stays empty.
    answer_html = "" if is_clarification else (_md.render(answer_markdown) if answer_markdown else "")
    return {
        "run_id": run.id,
        "question": run.question,
        "answer_markdown": answer_markdown,
        "answer_html": answer_html,
        "iteration_count": run.iteration_count,
        "tokens_input": run.tokens_input,
        "tokens_output": run.tokens_output,
        "status": run.status,
        "type": "clarification" if is_clarification else "answer",
        "clarification_question": answer_markdown if is_clarification else None,
        "steps": run.action_history or [],
        "dataset_ids": run.dataset_ids_json or [],
        # `suggested_questions` has no dedicated column today; read it defensively
        # so a future persisted column flows through, else fall back to [].
        "suggested_questions": getattr(run, "suggested_questions", None) or [],
        "prompt_breakdown": run.prompt_breakdown or {},
        "charts": run.charts_json or [],
    }


def _list_item(session: Session, row: ConversationSessionRow) -> dict:
    runs = _turn_runs(session, row.id)
    first_question = runs[0].question if runs else None
    return {
        "id": row.id,
        "name": row.name,
        "dataset_id": row.dataset_id,
        "dataset_ids": _session_datasets(row),
        "turn_count": len(runs),
        "first_question": first_question,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/sessions")
def list_sessions(session: Session = Depends(get_session)) -> dict:
    """All sessions, most-recently-updated first; each with a turn summary."""
    rows = (
        session.execute(
            select(ConversationSessionRow).order_by(
                ConversationSessionRow.updated_at.desc()
            )
        )
        .scalars()
        .all()
    )
    return ok([_list_item(session, r) for r in rows])


@router.get("/sessions/{session_id}")
def get_session_detail(session_id: str, session: Session = Depends(get_session)) -> dict:
    """One session plus its ordered `turns[]`."""
    row = session.get(ConversationSessionRow, session_id)
    if row is None:
        raise api_error("not_found", f"Session {session_id} not found", 404)

    runs = _turn_runs(session, session_id)
    return ok(
        {
            "id": row.id,
            "name": row.name,
            "dataset_id": row.dataset_id,
            "dataset_ids": _session_datasets(row),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "turns": [_turn_payload(r) for r in runs],
        }
    )


@router.patch("/sessions/{session_id}/name")
def rename_session(
    session_id: str,
    body: SessionRenameRequest,
    session: Session = Depends(get_session),
) -> dict:
    """Rename a session. 404 if missing."""
    row = session.get(ConversationSessionRow, session_id)
    if row is None:
        raise api_error("not_found", f"Session {session_id} not found", 404)
    row.name = body.name
    return ok({"id": row.id, "name": row.name})


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, session: Session = Depends(get_session)) -> dict:
    """Delete one session. Its runs reference it by `session_id` string, so
    removing the session row is sufficient (the runs are not orphan-crashed)."""
    row = session.get(ConversationSessionRow, session_id)
    if row is None:
        raise api_error("not_found", f"Session {session_id} not found", 404)
    session.delete(row)
    return ok({"deleted": session_id})


@router.delete("/sessions")
def delete_all_sessions(session: Session = Depends(get_session)) -> dict:
    """Delete every session. Always 200."""
    rows = session.execute(select(ConversationSessionRow)).scalars().all()
    for row in rows:
        session.delete(row)
    return ok({"deleted_count": len(rows)})


@router.get("/datasets/{dataset_id}/sessions")
def list_dataset_sessions(
    dataset_id: str, session: Session = Depends(get_session)
) -> dict:
    """Sessions scoped to one dataset (its single id OR a member of its id list).

    404 if the dataset itself is missing. Registered here (not in datasets.py) to
    keep file ownership disjoint; there is no `/sessions` sub-route in datasets.py
    so there is no path collision.
    """
    if session.get(DatasetRow, dataset_id) is None:
        raise api_error("not_found", f"Dataset {dataset_id} not found", 404)

    rows = (
        session.execute(
            select(ConversationSessionRow).order_by(
                ConversationSessionRow.updated_at.desc()
            )
        )
        .scalars()
        .all()
    )
    scoped = [r for r in rows if dataset_id in _session_datasets(r)]
    return ok([_list_item(session, r) for r in scoped])
