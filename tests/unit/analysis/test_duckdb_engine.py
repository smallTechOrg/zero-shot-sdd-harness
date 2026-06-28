"""Unit tests for the DuckDB analysis engine (pure, local, no LLM)."""
from pathlib import Path

import pytest

from analysis import (
    execute_sql,
    extract_schema,
    ingest_csv,
    profile_dataset,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
SALES_CSV = FIXTURES / "sales.csv"
MESSY_CSV = FIXTURES / "messy.csv"


@pytest.fixture
def sales_db(tmp_path):
    """Ingest the clean sales fixture into a fresh on-disk DuckDB file."""
    db_path = str(tmp_path / "sales.duckdb")
    ingest_csv(str(SALES_CSV), db_path)
    return db_path


@pytest.fixture
def messy_db(tmp_path):
    """Ingest the messy fixture into a fresh on-disk DuckDB file."""
    db_path = str(tmp_path / "messy.duckdb")
    ingest_csv(str(MESSY_CSV), db_path)
    return db_path


# --- ingest + schema ---------------------------------------------------------

def test_ingest_persists_on_disk_duckdb_file(tmp_path):
    db_path = tmp_path / "out.duckdb"
    ingest_csv(str(SALES_CSV), str(db_path))
    assert db_path.exists() and db_path.stat().st_size > 0


def test_extract_schema_returns_expected_columns_and_duckdb_types(sales_db):
    schema = extract_schema(sales_db)
    cols = {c["name"]: c["type"] for c in schema["columns"]}
    assert set(cols) == {"region", "month", "sales"}
    # DuckDB infers VARCHAR for text and a numeric type for the sales column
    assert cols["region"] == "VARCHAR"
    assert cols["sales"] in {"DOUBLE", "DECIMAL(18,3)", "FLOAT", "BIGINT"}
    # schema carries NO rows
    assert "rows" not in schema


# --- profile -----------------------------------------------------------------

def test_profile_reports_row_count(sales_db):
    profile = profile_dataset(sales_db)
    assert profile["row_count"] == 10


def test_profile_reports_nulls_and_distinct_per_column(sales_db):
    profile = profile_dataset(sales_db)
    by_name = {c["name"]: c for c in profile["columns"]}
    # one missing sales value in the fixture
    assert by_name["sales"]["nulls"] == 1
    # region has 4 distinct values: West/East/North/South
    assert by_name["region"]["distinct"] == 4
    assert by_name["region"]["nulls"] == 0


def test_profile_reports_min_max_for_numeric_columns(sales_db):
    profile = profile_dataset(sales_db)
    by_name = {c["name"]: c for c in profile["columns"]}
    assert by_name["sales"]["min"] == pytest.approx(250.0)
    assert by_name["sales"]["max"] == pytest.approx(2000.0)
    # non-numeric columns do not carry min/max
    assert "min" not in by_name["region"]
    assert "max" not in by_name["region"]


# --- execute_sql -------------------------------------------------------------

def test_execute_sql_group_by_returns_correct_aggregate_rows(sales_db):
    result = execute_sql(
        sales_db,
        "SELECT region, SUM(sales) AS total_sales FROM t "
        "GROUP BY region ORDER BY total_sales DESC",
    )
    assert result["columns"] == ["region", "total_sales"]
    totals = {row[0]: row[1] for row in result["rows"]}
    assert totals["West"] == pytest.approx(4500.0)
    assert totals["East"] == pytest.approx(2100.0)
    assert totals["South"] == pytest.approx(500.0)
    assert totals["North"] == pytest.approx(300.0)
    # ordered descending → West first
    assert result["rows"][0][0] == "West"


def test_execute_sql_returns_full_local_result_shape(sales_db):
    result = execute_sql(sales_db, "SELECT region, month, sales FROM t")
    assert set(result.keys()) == {"columns", "rows"}
    assert result["columns"] == ["region", "month", "sales"]
    assert len(result["rows"]) == 10


def test_execute_sql_raises_with_duckdb_error_text_on_invalid_sql(sales_db):
    # julianday is a SQLite-ism that DuckDB does not have → Catalog Error
    with pytest.raises(Exception) as exc:
        execute_sql(sales_db, "SELECT julianday(month) FROM t")
    msg = str(exc.value)
    assert "julianday" in msg
    # the raised exception must carry the DuckDB error text for the retry loop
    assert "Error" in msg


def test_execute_sql_raises_on_unknown_column(sales_db):
    with pytest.raises(Exception) as exc:
        execute_sql(sales_db, "SELECT no_such_col FROM t")
    assert "no_such_col" in str(exc.value)


# --- messy real-world data ---------------------------------------------------

def test_messy_csv_ingests_without_crashing(messy_db):
    schema = extract_schema(messy_db)
    names = {c["name"] for c in schema["columns"]}
    # odd column names with spaces / symbols survive ingest
    assert "Customer Name" in names
    assert "Order #" in names


def test_messy_csv_profiles_with_nulls(messy_db):
    profile = profile_dataset(messy_db)
    assert profile["row_count"] == 6
    by_name = {c["name"]: c for c in profile["columns"]}
    # the Amount column had a blank and an "N/A" → at least one null counted
    assert by_name["Amount (USD)"]["nulls"] >= 1


def test_messy_csv_query_runs_over_odd_column_names(messy_db):
    result = execute_sql(
        messy_db,
        'SELECT count(*) AS n FROM t WHERE "Notes" = \'paid\'',
    )
    assert result["rows"][0][0] == 3
