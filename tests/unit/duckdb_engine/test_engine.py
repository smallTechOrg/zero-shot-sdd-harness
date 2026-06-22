import csv
import json
import pytest
from pathlib import Path
from data_analyst.duckdb_engine.engine import register_dataset, execute_query, get_table_schema


@pytest.fixture()
def sample_csv(tmp_path) -> Path:
    p = tmp_path / "sample.csv"
    with p.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "value"])
        writer.writeheader()
        writer.writerows([
            {"name": "Alice", "value": "10"},
            {"name": "Bob", "value": "20"},
            {"name": "Carol", "value": "30"},
        ])
    return p


def test_register_csv_returns_row_count(sample_csv):
    count = register_dataset(
        session_id="test-session",
        table_name="t_sample",
        file_path=str(sample_csv),
        file_format="csv",
    )
    assert count == 3


def test_execute_query_count(sample_csv):
    register_dataset("s1", "t_test_count", str(sample_csv), "csv")
    results = execute_query("SELECT COUNT(*) AS cnt FROM t_test_count")
    assert results[0]["cnt"] == 3


def test_execute_query_returns_list_of_dicts(sample_csv):
    register_dataset("s2", "t_test_select", str(sample_csv), "csv")
    results = execute_query("SELECT name FROM t_test_select ORDER BY name")
    assert isinstance(results, list)
    assert isinstance(results[0], dict)
    assert results[0]["name"] == "Alice"


def test_get_table_schema(sample_csv):
    register_dataset("s3", "t_test_schema", str(sample_csv), "csv")
    schema = get_table_schema("t_test_schema")
    assert isinstance(schema, list)
    names = [c["name"] for c in schema]
    assert "name" in names
    assert "value" in names


def test_unsupported_format(tmp_path):
    p = tmp_path / "file.xyz"
    p.write_text("data")
    with pytest.raises(ValueError, match="Unsupported"):
        register_dataset("s4", "t_bad", str(p), "xyz")
