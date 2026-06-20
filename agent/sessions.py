import io
import re
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

current_session_id: ContextVar[str | None] = ContextVar("current_session_id", default=None)


@dataclass
class SessionResources:
    by_id: dict[str, Any] = field(default_factory=dict)


_SESSIONS: dict[str, SessionResources] = {}


def get_session(session_id: str) -> SessionResources:
    return _SESSIONS.setdefault(session_id, SessionResources())


def release_session(session_id: str) -> None:
    """Drop a session's resources — call ONLY on explicit session delete, NEVER per question."""
    _SESSIONS.pop(session_id, None)


def load_resource(session_id: str, data: str, resource_id: str = "main") -> str:
    """Load a dataset (CSV/JSON) or plain text into the session bag.
    CSV/JSON → stored as a pandas DataFrame under sess.by_id['df'].
    Plain text → stored as text chunks under sess.by_id['chunks'] (legacy fallback).
    Persists across follow-up turns; released only on explicit session delete."""
    import pandas as pd
    sess = get_session(session_id)
    raw = data if isinstance(data, str) else data.decode("utf-8", errors="replace")

    # Try CSV first (most common for data analysis)
    try:
        df = pd.read_csv(io.StringIO(raw))
        if df.shape[1] > 1:          # at least 2 columns → treat as structured data
            sess.by_id["df"] = df
            return resource_id
    except Exception:
        pass

    # Try JSON (records or columns orientation)
    try:
        df = pd.read_json(io.StringIO(raw))
        if df.shape[1] > 1:
            sess.by_id["df"] = df
            return resource_id
    except Exception:
        pass

    # Fall back to plain-text document (legacy: chunk on blank lines)
    chunks = [c.strip() for c in re.split(r"\n\s*\n", raw) if c.strip()]
    sess.by_id["chunks"] = chunks or [raw.strip()]
    return resource_id
