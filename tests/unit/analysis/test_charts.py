from analysis.charts import VEGA_LITE_SCHEMA, build_vega_spec


def _table():
    return [
        {"region": "North", "amount": 1600000},
        {"region": "South", "amount": 900000},
    ]


def test_valid_selection_builds_spec_with_embedded_table():
    table = _table()
    selection = {"mark": "bar", "x": "region", "y": "amount", "title": "Sales"}
    spec = build_vega_spec(selection, table)

    assert spec["$schema"] == VEGA_LITE_SCHEMA
    assert spec["mark"] == "bar"
    assert spec["data"]["values"] == table
    assert spec["encoding"]["x"]["field"] == "region"
    assert spec["encoding"]["y"]["field"] == "amount"
    assert spec["encoding"]["y"]["type"] == "quantitative"
    assert spec["title"] == "Sales"


def test_invalid_columns_falls_back_but_keeps_data():
    table = _table()
    # x/y reference columns that do not exist -> fallback.
    spec = build_vega_spec({"mark": "line", "x": "nope", "y": "gone"}, table)
    assert spec["$schema"] == VEGA_LITE_SCHEMA
    assert "mark" in spec
    assert spec["data"]["values"] == table
    # Fallback picks the categorical vs numeric columns.
    assert spec["encoding"]["x"]["field"] == "region"
    assert spec["encoding"]["y"]["field"] == "amount"


def test_empty_selection_returns_renderable_fallback():
    spec = build_vega_spec({}, _table())
    assert spec["$schema"] == VEGA_LITE_SCHEMA
    assert "mark" in spec
    assert spec["data"]["values"] == _table()


def test_none_selection_and_empty_table_never_raises():
    spec = build_vega_spec(None, [])
    assert spec["$schema"] == VEGA_LITE_SCHEMA
    assert "mark" in spec
    assert spec["data"]["values"] == []
