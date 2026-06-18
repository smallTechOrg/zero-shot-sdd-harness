"""Unit tests for CSV ingest, the read-only SQL guard, and DuckDB query — no LLM."""

from __future__ import annotations

import uuid

import pytest

from datachat.data import engine
from datachat.data.ingest import ingest_csv
from datachat.data.query import QueryError, inspect_schema, run_sql
from datachat.guardrails.sql_safety import SqlSafetyError, validate_read_only

CSV = b"region,sales\nwest,100\neast,200\nwest,50\n"


@pytest.fixture
def dataset_id():
    ds = str(uuid.uuid4())
    yield ds
    engine.release(ds)


def test_ingest_infers_schema_and_sample(dataset_id):
    res = ingest_csv(dataset_id, "sales.csv", CSV)
    assert res.row_count == 3
    names = {c["name"] for c in res.schema_columns}
    assert names == {"region", "sales"}
    assert res.duckdb_table.startswith("ds_")
    assert len(res.sample_rows) == 3


def test_ingest_then_query(dataset_id):
    ingest_csv(dataset_id, "sales.csv", CSV)
    table = inspect_schema(dataset_id)["tables"][0]["table"]
    out = run_sql(
        dataset_id,
        f'SELECT region, sum(sales) AS total FROM "{table}" GROUP BY region ORDER BY region',
    )
    assert out["columns"] == ["region", "total"]
    assert out["rows"] == [["east", 200], ["west", 150]]


def test_inspect_schema_lists_tables(dataset_id):
    ingest_csv(dataset_id, "sales.csv", CSV)
    schema = inspect_schema(dataset_id)
    assert len(schema["tables"]) == 1
    cols = {c["name"] for c in schema["tables"][0]["columns"]}
    assert cols == {"region", "sales"}


@pytest.mark.parametrize(
    "bad",
    [
        "DROP TABLE foo",
        "DELETE FROM foo",
        "INSERT INTO foo VALUES (1)",
        "UPDATE foo SET x=1",
        "CREATE TABLE bar AS SELECT 1",
        "ATTACH 'x.db'",
        "COPY foo TO 'out.csv'",
        "SELECT 1; DROP TABLE foo",
        "PRAGMA database_list",
    ],
)
def test_safety_rejects_writes(bad):
    with pytest.raises(SqlSafetyError):
        validate_read_only(bad)


@pytest.mark.parametrize(
    "good",
    [
        "SELECT 1",
        "SELECT * FROM t WHERE x > 1",
        "WITH c AS (SELECT 1 AS n) SELECT n FROM c",
        "select region, count(*) from t group by region",
    ],
)
def test_safety_allows_selects(good):
    assert validate_read_only(good)


def test_query_rejection_is_recoverable_value(dataset_id):
    ingest_csv(dataset_id, "sales.csv", CSV)
    with pytest.raises(QueryError):
        run_sql(dataset_id, "DROP TABLE foo")


def test_query_missing_session(dataset_id):
    with pytest.raises(QueryError, match="re-upload"):
        run_sql(dataset_id, "SELECT 1")
