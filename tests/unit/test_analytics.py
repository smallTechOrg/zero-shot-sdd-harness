"""Unit tests for ingest + DuckDB store — no LLM key required."""
import pytest

from analytics.ingest import ingest_csv, IngestError
from analytics.duckdb_store import DuckDBStore, NonSelectError

CSV = b"region,revenue\nNorth,100\nSouth,250\nNorth,50\n"


def test_ingest_creates_table_and_schema():
    row_count, schema = ingest_csv(content=CSV, table="ds_test")
    assert row_count == 3
    names = [c["name"] for c in schema]
    assert names == ["region", "revenue"]
    # every column carries a duckdb type string
    assert all(c["type"] for c in schema)


def test_ingest_rejects_empty():
    with pytest.raises(IngestError):
        ingest_csv(content=b"", table="ds_empty")


def test_ingest_rejects_no_data_rows():
    with pytest.raises(IngestError):
        ingest_csv(content=b"a,b,c\n", table="ds_headeronly")


def test_store_runs_select():
    ingest_csv(content=CSV, table="ds_q")
    cols, rows = DuckDBStore().execute_select(
        "SELECT region, SUM(revenue) AS total FROM ds_q GROUP BY region ORDER BY region"
    )
    assert cols == ["region", "total"]
    data = {r[0]: r[1] for r in rows}
    assert data["North"] == 150
    assert data["South"] == 250


@pytest.mark.parametrize("sql", [
    "DROP TABLE ds_q",
    "INSERT INTO ds_q VALUES ('X', 1)",
    "UPDATE ds_q SET revenue = 0",
    "DELETE FROM ds_q",
    "SELECT 1; DROP TABLE ds_q",
])
def test_store_rejects_non_select(sql):
    with pytest.raises(NonSelectError):
        DuckDBStore().execute_select(sql)
