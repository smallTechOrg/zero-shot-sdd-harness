"""DB session + model integration tests — no LLM key required."""


def test_session_upsert(_isolated_db):
    """Insert and retrieve a SessionRow."""
    from db.session import create_db_session
    from db.models import SessionRow

    with create_db_session() as session:
        row = SessionRow(id="test-123")
        session.add(row)

    with create_db_session() as session:
        fetched = session.get(SessionRow, "test-123")
        assert fetched is not None
        assert fetched.id == "test-123"


def test_dataset_row_persists(_isolated_db):
    """DatasetRow can be written and read back."""
    from db.session import create_db_session
    from db.models import SessionRow, DatasetRow

    with create_db_session() as session:
        sess = SessionRow(id="sess-1")
        session.add(sess)
        ds = DatasetRow(
            session_id="sess-1",
            table_name="sess_1_myfile",
            original_filename="myfile.csv",
            row_count=42,
            column_names='["a","b"]',
        )
        session.add(ds)
        session.flush()
        ds_id = ds.id

    with create_db_session() as session:
        fetched = session.get(DatasetRow, ds_id)
        assert fetched is not None
        assert fetched.row_count == 42
        assert fetched.table_name == "sess_1_myfile"


def test_audit_log_row_persists(_isolated_db):
    """AuditLogRow can be written and read back."""
    from db.session import create_db_session
    from db.models import AuditLogRow

    with create_db_session() as session:
        row = AuditLogRow(
            session_id="sess-1",
            dataset_table="sess_1_test",
            question="How many rows?",
            sql_generated="SELECT COUNT(*) FROM test",
            row_count=5,
            duration_ms=42,
        )
        session.add(row)
        session.flush()
        row_id = row.id

    with create_db_session() as session:
        fetched = session.get(AuditLogRow, row_id)
        assert fetched is not None
        assert fetched.sql_generated == "SELECT COUNT(*) FROM test"
        assert fetched.error is None


def test_reset_engine():
    """reset_engine() sets singletons to None."""
    from db import session as session_module
    session_module.reset_engine()
    assert session_module._engine is None
    assert session_module._SessionLocal is None
