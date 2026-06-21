import json

import duckdb
import pytest

from src.db.schema import create_tables
from src.datasets.ingest import ingest_file


@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def csv_file(tmp_path):
    f = tmp_path / "sales.csv"
    f.write_text("product,revenue\nwidget,100\ngadget,200\n")
    return str(f)


@pytest.fixture
def json_file(tmp_path):
    f = tmp_path / "events.json"
    f.write_text(json.dumps([{"event": "click", "count": 5}, {"event": "view", "count": 10}]))
    return str(f)


def test_ingest_csv(db, csv_file):
    result = ingest_file(db, csv_file, "sales")
    assert result["name"] == "sales"
    assert result["file_type"] == "csv"
    assert result["row_count"] == 2
    assert "product" in result["columns"]
    assert "revenue" in result["columns"]


def test_csv_registered_in_datasets_table(db, csv_file):
    ingest_file(db, csv_file, "sales")
    row = db.execute("SELECT name, file_type FROM datasets WHERE name = 'sales'").fetchone()
    assert row is not None
    assert row[1] == "csv"


def test_csv_queryable_as_view(db, csv_file):
    ingest_file(db, csv_file, "sales")
    rows = db.execute("SELECT revenue FROM sales ORDER BY revenue").fetchall()
    assert rows == [(100,), (200,)]


def test_ingest_json(db, json_file):
    result = ingest_file(db, json_file, "events")
    assert result["name"] == "events"
    assert result["file_type"] == "json"
    assert result["row_count"] == 2


def test_unsupported_type_raises(db, tmp_path):
    bad = tmp_path / "file.xml"
    bad.write_text("<root/>")
    with pytest.raises(ValueError, match="Unsupported"):
        ingest_file(db, str(bad), "bad")


def test_duplicate_name_raises(db, csv_file):
    ingest_file(db, csv_file, "sales")
    with pytest.raises(Exception):  # DuckDB UNIQUE constraint
        ingest_file(db, csv_file, "sales")


@pytest.fixture
def parquet_file(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.table({"x": [1, 2, 3], "y": [4, 5, 6]})
    f = tmp_path / "data.parquet"
    pq.write_table(table, f)
    return str(f)


def test_ingest_parquet(db, parquet_file):
    result = ingest_file(db, parquet_file, "pdata")
    assert result["file_type"] == "parquet"
    assert result["row_count"] == 3


@pytest.fixture
def excel_file(tmp_path):
    import pandas as pd

    f = tmp_path / "report.xlsx"
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_excel(f, index=False)
    return str(f)


def test_ingest_excel(db, excel_file):
    result = ingest_file(db, excel_file, "report")
    assert result["file_type"] == "excel"
    assert result["row_count"] == 2
