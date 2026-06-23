"""Ingest utility unit tests — no LLM key required."""
from ingest.loader import _sanitize_name, _session_prefix


def test_sanitize_name_basic():
    assert _sanitize_name("Sales Report 2024.csv") == "sales_report_2024"


def test_sanitize_name_special_chars():
    result = _sanitize_name("My Data (Q3)!.xlsx")
    # Result should be alphanumeric + underscore only
    assert all(c.isalnum() or c == "_" for c in result)


def test_sanitize_name_leading_digit():
    result = _sanitize_name("2024_sales.csv")
    assert not result[0].isdigit()


def test_sanitize_name_no_extension():
    result = _sanitize_name("myfile")
    assert result == "myfile"


def test_sanitize_name_max_length():
    long_name = "a" * 100 + ".csv"
    result = _sanitize_name(long_name)
    assert len(result) <= 50


def test_session_prefix_replaces_hyphens():
    result = _session_prefix("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    assert "-" not in result
    assert result == "a1b2c3d4_e5f6_7890_abcd_ef1234567890"


def test_session_prefix_no_hyphens():
    result = _session_prefix("nohyphens")
    assert result == "nohyphens"
