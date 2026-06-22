from data_analyst.db.models import AuditLogEntryRow, DatasetRow, MessageRow, SessionRow
from data_analyst.db.session import create_db_session
from data_analyst.graph.runner import run_question
from data_analyst.tools import duck


def _seed_dataset(session_id: int, tmp_path) -> None:
    csv = tmp_path / "invoices.csv"
    csv.write_text("customer,amount\nA,100\nB,200\nA,50\n")
    table = duck.sanitize_table_name(f"s{session_id}_invoices")
    row_count, schema = duck.ingest_file(str(csv), table, "csv")
    samples = duck.get_sample_rows(table, 5)
    with create_db_session() as session:
        session.add(
            DatasetRow(
                session_id=session_id,
                name="invoices",
                source_filename="invoices.csv",
                file_format="csv",
                duckdb_table=table,
                row_count=row_count,
                schema_json=[c.model_dump() for c in schema],
                sample_rows_json=samples,
            )
        )


def test_pipeline_runs_end_to_end(tmp_path):
    with create_db_session() as session:
        s = SessionRow(name="test session")
        session.add(s)
        session.flush()
        session_id = s.id

    _seed_dataset(session_id, tmp_path)

    result = run_question(session_id, "how many invoice rows are there?")

    assert result["status"] == "completed"
    assert result["answer_text"]
    assert result["generated_sql"]
    assert result["audit_entry_id"] is not None

    with create_db_session() as session:
        audit = (
            session.query(AuditLogEntryRow)
            .filter(AuditLogEntryRow.session_id == session_id)
            .all()
        )
        assert any(a.status == "success" for a in audit)
        messages = (
            session.query(MessageRow)
            .filter(MessageRow.session_id == session_id)
            .all()
        )
        assert any(m.role == "assistant" for m in messages)


def test_pipeline_with_no_datasets_is_handled(tmp_path):
    with create_db_session() as session:
        s = SessionRow(name="empty")
        session.add(s)
        session.flush()
        session_id = s.id

    result = run_question(session_id, "anything?")
    assert result["status"] == "failed"
    assert "No datasets" in (result["answer_text"] or "")
