"""Unit tests for the keyset (cursor) pagination helper backing the AJAX-loaded UI lists."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from data_analysis_agent.api._pagination import (
    InvalidCursor,
    decode_cursor,
    encode_cursor,
    keyset_page,
)
from data_analysis_agent.db.models import Base, SessionRow


def _session_with_rows(n: int) -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = Session(engine)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        s.add(SessionRow(id=f"id{i:02d}", name=f"s{i}",
                         created_at=base + timedelta(minutes=i),
                         updated_at=base + timedelta(minutes=i)))
    s.commit()
    return s


def _page(s, cursor, limit, descending):
    return keyset_page(s.query(SessionRow), sort_col=SessionRow.created_at, id_col=SessionRow.id,
                       sort_attr="created_at", cursor=cursor, limit=limit, descending=descending)


def test_cursor_roundtrip():
    dt = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert decode_cursor(encode_cursor(dt, "abc")) == (dt, "abc")
    assert decode_cursor(None) is None


def test_decode_invalid_raises():
    with pytest.raises(InvalidCursor):
        decode_cursor("@@@ not a cursor @@@")


def test_descending_walk_to_exhaustion():
    s = _session_with_rows(7)
    rows, cur = _page(s, None, 3, True)
    assert [r.name for r in rows] == ["s6", "s5", "s4"] and cur
    rows2, cur2 = _page(s, cur, 3, True)
    assert [r.name for r in rows2] == ["s3", "s2", "s1"] and cur2
    rows3, cur3 = _page(s, cur2, 3, True)
    assert [r.name for r in rows3] == ["s0"]
    assert cur3 is None                                  # last page → no next cursor


def test_ascending_exact_limit_has_no_next():
    s = _session_with_rows(4)
    rows, cur = _page(s, None, 4, False)
    assert [r.name for r in rows] == ["s0", "s1", "s2", "s3"]
    assert cur is None                                   # exactly `limit` rows → no further page
