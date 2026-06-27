"""Keyset (cursor) pagination for the server-rendered UI lists.

The UI loads every list by AJAX after the shell renders and pages it with **Previous / Next** buttons.
Each page is one keyset window of an ordered query; the server returns an opaque ``next_cursor`` (forward
only) and the client keeps a small stack of the cursors it has visited so "Previous" is just stepping
back in that stack. The cursor encodes the last row's ``(sort_value, id)`` — the same opaque-base64
scheme the MCP JSON-RPC surface uses (``tools/mcp/dispatch.py``), so both surfaces paginate identically.
"""
from __future__ import annotations

import base64
from datetime import datetime

from sqlalchemy import and_, or_


class InvalidCursor(Exception):
    """Raised when a client supplies a cursor that cannot be decoded."""


def encode_cursor(sort_value, row_id: str) -> str:
    """Opaque cursor for the last row of a page: base64 of ``<sort_value>|<id>``."""
    raw = f"{sort_value.isoformat() if isinstance(sort_value, datetime) else sort_value}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str | None) -> tuple | None:
    """Decode a cursor to ``(sort_value, id)`` (``sort_value`` parsed as a datetime), or ``None``."""
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        sort_value, row_id = raw.split("|", 1)
        return datetime.fromisoformat(sort_value), row_id
    except Exception as exc:  # malformed / tampered cursor
        raise InvalidCursor("Invalid cursor.") from exc


def keyset_page(
    query,
    *,
    sort_col,
    id_col,
    sort_attr: str,
    cursor: str | None,
    limit: int,
    descending: bool = False,
) -> tuple[list, str | None]:
    """Return ``(rows, next_cursor)`` for one keyset window of ``query``.

    Pages by the strict ``(sort_col, id_col)`` tuple ordering (ascending or descending) so there is no
    offset drift on concurrent inserts. Fetches ``limit + 1`` rows to know whether a further page exists
    without a separate COUNT; ``next_cursor`` is ``None`` on the last page. ``sort_attr`` names the
    row attribute the cursor is built from (must match ``sort_col``).
    """
    decoded = decode_cursor(cursor)
    if decoded is not None:
        sort_value, row_id = decoded
        if descending:
            query = query.filter(
                or_(sort_col < sort_value, and_(sort_col == sort_value, id_col < row_id))
            )
        else:
            query = query.filter(
                or_(sort_col > sort_value, and_(sort_col == sort_value, id_col > row_id))
            )
    order = (sort_col.desc(), id_col.desc()) if descending else (sort_col.asc(), id_col.asc())
    rows = query.order_by(*order).limit(limit + 1).all()
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = encode_cursor(getattr(last, sort_attr), last.id)
    return rows, next_cursor
