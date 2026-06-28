"""Unit tests for the deterministic chart-type heuristic (no LLM)."""
from analysis import pick_chart, to_aggregate
from analysis.charts import AGG_ROW_CAP


# --- pick_chart --------------------------------------------------------------

def test_categorical_dimension_with_numeric_measure_picks_bar():
    aggregate = {
        "columns": ["region", "total_sales"],
        "rows": [["West", 4500.0], ["East", 2100.0], ["North", 300.0]],
    }
    chart = pick_chart(aggregate)
    assert chart["type"] == "bar"
    assert chart["x"] == "region"
    assert chart["y"] == "total_sales"


def test_time_dimension_with_numeric_measure_picks_line():
    aggregate = {
        "columns": ["month", "total_sales"],
        "rows": [["2024-01", 1800.0], ["2024-02", 2450.0], ["2024-03", 2900.0]],
    }
    chart = pick_chart(aggregate)
    assert chart["type"] == "line"
    assert chart["x"] == "month"
    assert chart["y"] == "total_sales"


def test_small_part_of_whole_picks_pie():
    aggregate = {
        "columns": ["category", "share"],
        "rows": [["A", 60.0], ["B", 40.0]],
    }
    chart = pick_chart(aggregate)
    assert chart["type"] == "pie"
    assert chart["x"] == "category"
    assert chart["y"] == "share"


def test_single_scalar_result_falls_back_to_table():
    aggregate = {"columns": ["total_sales"], "rows": [[7400.0]]}
    chart = pick_chart(aggregate)
    assert chart["type"] == "table"


def test_multiple_measures_fall_back_to_table():
    aggregate = {
        "columns": ["region", "total_sales", "avg_sales", "max_sales"],
        "rows": [["West", 4500.0, 1500.0, 2000.0]],
    }
    chart = pick_chart(aggregate)
    assert chart["type"] == "table"


def test_no_numeric_measure_falls_back_to_table():
    aggregate = {
        "columns": ["region", "month"],
        "rows": [["West", "2024-01"], ["East", "2024-02"]],
    }
    chart = pick_chart(aggregate)
    assert chart["type"] == "table"


def test_empty_result_falls_back_to_table():
    chart = pick_chart({"columns": [], "rows": []})
    assert chart["type"] == "table"


# --- to_aggregate (the privacy/aggregate cap helper) -------------------------

def test_to_aggregate_caps_rows_at_default_50():
    result = {"columns": ["i", "v"], "rows": [[i, i * 1.0] for i in range(200)]}
    aggregate = to_aggregate(result)
    assert len(aggregate["rows"]) == AGG_ROW_CAP == 50
    assert aggregate["truncated"] is True
    assert aggregate["total_rows"] == 200


def test_to_aggregate_preserves_columns_and_small_results_untruncated():
    result = {"columns": ["region", "total"], "rows": [["West", 4500.0], ["East", 2100.0]]}
    aggregate = to_aggregate(result)
    assert aggregate["columns"] == ["region", "total"]
    assert aggregate["rows"] == [["West", 4500.0], ["East", 2100.0]]
    assert aggregate["truncated"] is False
    assert aggregate["total_rows"] == 2


def test_to_aggregate_respects_custom_cap():
    result = {"columns": ["i"], "rows": [[i] for i in range(10)]}
    aggregate = to_aggregate(result, cap=3)
    assert len(aggregate["rows"]) == 3
    assert aggregate["truncated"] is True
