import uuid
from datetime import datetime, UTC

import aiosqlite
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.config import get_settings

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", status_code=201)
async def create_session():
    settings = get_settings()
    session_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    name = f"Session-{session_id[:8]}"

    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute(
            "INSERT INTO session (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, name, now, now),
        )
        await db.commit()

    return JSONResponse(
        status_code=201,
        headers={"Location": f"/sessions/{session_id}"},
        content={"id": session_id, "name": name, "created_at": now},
    )


@router.get("")
async def list_sessions():
    settings = get_settings()
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, created_at, updated_at FROM session ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
    return {"sessions": [dict(r) for r in rows]}


@router.get("/{session_id}/history")
async def get_session_history(session_id: str):
    raise HTTPException(
        status_code=404,
        detail={"error": {"code": "NOT_YET", "message": "Session history available in Phase 2"}},
    )


@router.get("/{session_id}")
async def get_session(session_id: str):
    settings = get_settings()
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, created_at, updated_at FROM session WHERE id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NO_SESSION", "message": "Session not found"}},
        )
    return dict(row)
