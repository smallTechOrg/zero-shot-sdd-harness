import sqlite3

import pytest

from data.ingest import ingest_file
from data.schema_summary import sample_rows, schema_summary
from data.executor import run_read_only
from db.models import AuditLogRow, DatasetRow
from db.session import create_db_session

CSV = b"region,revenue\nWest,9000\nEast,7000\nNorth,3000\n"


def test_ingest_creates_table_and_metadata():
    result = ingest_file(CSV, "sales.csv", session_id="sess-1")

    assert result["row_count"] == 3
    assert result["table_name"].startswith("ds_")
    names = {c["name"]: c["type"] for c in result["columns"]}
    assert names["region"] == "TEXT"
    assert names["revenue"] == "INTEGER"

    with create_db_session() as s:
        ds = s.query(DatasetRow).filter_by(id=result["dataset_id"]).one()
        assert ds.row_count == 3
        assert ds.original_filename == "sales.csv"

        audit_rows = (
            s.query(AuditLogRow)
            .filter_by(operation="ingest", session_id="sess-1")
            .all()
        )
        assert len(audit_rows) == 1
        assert audit_rows[0].success is True
        assert audit_rows[0].rows_returned == 3


def test_schema_summary_and_sample_rows():
    result = ingest_file(CSV, "sales.csv", session_id="sess-2")
    table = result["table_name"]

    cols = schema_summary(table)
    assert {c["name"] for c in cols} == {"region", "revenue"}

    sample = sample_rows(table, n=5)
    assert sample["columns"] == ["region", "revenue"]
    assert len(sample["rows"]) == 3  # only 3 rows exist

    limited = sample_rows(table, n=2)
    assert len(limited["rows"]) == 2


def test_run_read_only_returns_rows():
    result = ingest_file(CSV, "sales.csv", session_id="sess-3")
    table = result["table_name"]

    out = run_read_only(f'SELECT region, revenue FROM "{table}" ORDER BY revenue DESC')
    assert out["columns"] == ["region", "revenue"]
    assert out["rows"][0] == ["West", 9000]


def test_run_read_only_blocks_writes():
    result = ingest_file(CSV, "sales.csv", session_id="sess-4")
    table = result["table_name"]

    with pytest.raises(sqlite3.OperationalError):
        run_read_only(f'DELETE FROM "{table}"')


def test_ingest_empty_raises():
    with pytest.raises(ValueError):
        ingest_file(b"", "empty.csv", session_id="sess-5")
