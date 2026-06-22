"""Metadata-DB model tests — no LLM key required."""
from sqlalchemy.orm import Session

from db.models import Dataset, Session as SessionRow, Message, AuditLog


def test_dataset_roundtrip(_isolated_db):
    with Session(_isolated_db) as s:
        d = Dataset(name="orders.csv", duckdb_table="ds_1",
                    schema_json='[{"name": "x", "type": "BIGINT"}]', row_count=42)
        s.add(d)
        s.commit()
        did = d.id
    with Session(_isolated_db) as s:
        got = s.get(Dataset, did)
        assert got.name == "orders.csv"
        assert got.row_count == 42


def test_session_default_title(_isolated_db):
    with Session(_isolated_db) as s:
        sess = SessionRow()
        s.add(sess)
        s.commit()
        assert sess.title == "New session"


def test_message_and_audit(_isolated_db):
    with Session(_isolated_db) as s:
        sess = SessionRow()
        s.add(sess)
        s.flush()
        m = Message(session_id=sess.id, role="user", content="hi")
        a = AuditLog(session_id=sess.id, operation="query", status="success", row_count=3)
        s.add_all([m, a])
        s.commit()
        assert m.id and a.id
        assert m.sql is None and m.result_json is None
