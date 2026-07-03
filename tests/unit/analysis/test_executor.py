import pandas as pd

from analysis.executor import run_pandas


def _write_csv(tmp_path):
    p = tmp_path / "data.csv"
    pd.DataFrame(
        {
            "g": ["x", "y", "x", "y", "x"],
            "a": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    ).to_csv(p, index=False)
    return str(p)


def test_run_pandas_happy_path_full_data(tmp_path):
    data_path = _write_csv(tmp_path)
    code = (
        "result = {"
        "  'value': float(df['a'].sum()),"
        "  'table': df.groupby('g')['a'].sum().reset_index().to_dict('records'),"
        "  'columns': ['g', 'a'],"
        "}"
    )
    result, error = run_pandas(code, data_path, "csv", timeout=30)

    assert error is None
    assert result is not None
    # Full-data sum, not a sample.
    assert result["value"] == 15.0
    by_g = {row["g"]: row["a"] for row in result["table"]}
    assert by_g == {"x": 9.0, "y": 6.0}
    assert result["columns"] == ["g", "a"]


def test_run_pandas_code_error_returns_error(tmp_path):
    data_path = _write_csv(tmp_path)
    result, error = run_pandas("result = 1 / 0", data_path, "csv", timeout=30)
    assert result is None
    assert error and isinstance(error, str)
    assert "ZeroDivisionError" in error or "division" in error.lower()


def test_run_pandas_missing_result_returns_error(tmp_path):
    data_path = _write_csv(tmp_path)
    result, error = run_pandas("x = df['a'].sum()", data_path, "csv", timeout=30)
    assert result is None
    assert error and "result" in error.lower()


def test_run_pandas_timeout_returns_error_not_raised(tmp_path):
    data_path = _write_csv(tmp_path)
    result, error = run_pandas(
        "import time; time.sleep(5)", data_path, "csv", timeout=1
    )
    assert result is None
    assert error and "time" in error.lower()


def test_run_pandas_truncates_huge_table(tmp_path):
    data_path = _write_csv(tmp_path)
    code = (
        "result = {"
        "  'value': None,"
        "  'table': [{'i': i} for i in range(2500)],"
        "  'columns': ['i'],"
        "}"
    )
    result, error = run_pandas(code, data_path, "csv", timeout=30)
    assert error is None
    assert len(result["table"]) == 2000
    assert result.get("table_truncated") is True
