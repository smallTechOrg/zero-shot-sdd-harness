import pandas as pd
import pytest

from analysis.loader import detect_format, load_dataframe


def test_detect_format_csv_and_xlsx():
    assert detect_format("sales_2024.csv") == "csv"
    assert detect_format("Report.CSV") == "csv"
    assert detect_format("book.xlsx") == "xlsx"
    assert detect_format("legacy.xls") == "xlsx"


def test_detect_format_unsupported_raises():
    with pytest.raises(ValueError):
        detect_format("data.json")
    with pytest.raises(ValueError):
        detect_format("noextension")


def test_load_dataframe_csv(tmp_path):
    p = tmp_path / "d.csv"
    pd.DataFrame({"a": [1, 2, 3], "g": ["x", "y", "x"]}).to_csv(p, index=False)

    df = load_dataframe(str(p), "csv")
    assert list(df.columns) == ["a", "g"]
    assert len(df) == 3


def test_load_dataframe_unsupported_format_raises(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        load_dataframe(str(p), "parquet")


def test_load_dataframe_empty_file_raises(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("")
    with pytest.raises(ValueError):
        load_dataframe(str(p), "csv")
