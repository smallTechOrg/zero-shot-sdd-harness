"""ORM model unit tests — no LLM key required."""
from db.models import SessionRow, DatasetRow, AuditLogRow


def test_session_row_fields():
    row = SessionRow(id="test-session")
    assert row.id == "test-session"
    # created_at / last_seen_at defaults fire at insert — just check attribute exists
    assert hasattr(row, "created_at")
    assert hasattr(row, "last_seen_at")


def test_dataset_row_defaults():
    row = DatasetRow(
        session_id="s1",
        table_name="s1_test",
        original_filename="test.csv",
        row_count=10,
        column_names='["a","b"]',
    )
    # id default (_uuid) fires at construction time via default=
    assert row.session_id == "s1"
    assert row.table_name == "s1_test"
    assert row.row_count == 10


def test_audit_log_row_nullable_fields():
    row = AuditLogRow(
        session_id="s1",
        dataset_table="s1_test",
        question="How many rows?",
    )
    assert row.sql_generated is None
    assert row.error is None
    assert row.row_count is None
    assert row.duration_ms is None
