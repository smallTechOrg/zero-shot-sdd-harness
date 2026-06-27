"""Phase 1 — Analysis endpoint + graph tests."""
import io
import json

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def multi_column_csv_bytes() -> bytes:
    """Multi-column numeric DataFrame for stat testing."""
    df = pd.DataFrame({
        "age": [22, 35, 28, 45, 31],
        "salary": [50000.0, 80000.0, 65000.0, 120000.0, 72000.0],
        "years_exp": [1, 8, 4, 15, 6],
        "department": ["Eng", "Sales", "Eng", "HR", "Eng"],  # non-numeric — should be ignored
    })
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


@pytest.fixture
def upload_id(api_client, multi_column_csv_bytes) -> str:
    """Upload a CSV and return its upload_id."""
    resp = api_client.post(
        "/uploads",
        files={"file": ("data.csv", multi_column_csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["upload_id"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def post_analysis(api_client, upload_id: str, analysis_type: str, params: dict | None = None):
    return api_client.post(
        "/analyses",
        json={"upload_id": upload_id, "analysis_type": analysis_type, "params": params or {}},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_summary_stats_returns_summary_and_chart_and_table(api_client, upload_id):
    """summary_stats analysis returns a non-empty summary, valid chart_json, and table rows."""
    resp = post_analysis(api_client, upload_id, "summary_stats")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["error"] is None
    data = body["data"]

    # summary is a non-empty string
    assert data["summary"] and isinstance(data["summary"], str)

    # chart_json is a valid JSON string
    assert data["chart_json"] and isinstance(data["chart_json"], str)
    parsed_chart = json.loads(data["chart_json"])
    assert "data" in parsed_chart  # Plotly figure has a "data" key

    # table has one row per numeric column (3 numeric cols: age, salary, years_exp)
    table = data["table"]
    assert isinstance(table, list)
    assert len(table) == 3
    col_names_in_table = {row["column"] for row in table}
    assert "age" in col_names_in_table
    assert "salary" in col_names_in_table
    assert "years_exp" in col_names_in_table

    # Each table row has the expected stat keys
    for row in table:
        for key in ("column", "count", "mean", "median", "min", "max", "std"):
            assert key in row, f"Missing key '{key}' in table row: {row}"


def test_summary_stats_stat_values_correct(api_client, upload_id):
    """Verify computed statistics match expected values for the 'age' column."""
    resp = post_analysis(api_client, upload_id, "summary_stats")
    assert resp.status_code == 200, resp.text
    table = resp.json()["data"]["table"]
    age_row = next((r for r in table if r["column"] == "age"), None)
    assert age_row is not None, "No row for 'age' in table"

    assert age_row["count"] == 5
    assert abs(age_row["mean"] - 32.2) < 0.01
    assert age_row["min"] == 22.0
    assert age_row["max"] == 45.0
    assert age_row["median"] == 31.0


def test_summary_stats_status_is_completed(api_client, upload_id):
    """A successful summary_stats analysis has status='completed'."""
    resp = post_analysis(api_client, upload_id, "summary_stats")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "completed"


def test_trend_over_time_is_phase2_stub(api_client, upload_id):
    """trend_over_time returns Phase 2 stub (summary='Coming in Phase 2', not an error)."""
    resp = post_analysis(api_client, upload_id, "trend_over_time")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["summary"] == "Coming in Phase 2"
    assert data["chart_json"] is None
    assert data["table"] is None
    # status should be completed (not failed)
    assert data["status"] == "completed"


def test_top_bottom_n_is_phase2_stub(api_client, upload_id):
    """top_bottom_n returns Phase 2 stub."""
    resp = post_analysis(api_client, upload_id, "top_bottom_n")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["summary"] == "Coming in Phase 2"
    assert data["status"] == "completed"


def test_correlation_is_phase2_stub(api_client, upload_id):
    """correlation returns Phase 2 stub."""
    resp = post_analysis(api_client, upload_id, "correlation")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["summary"] == "Coming in Phase 2"
    assert data["status"] == "completed"


def test_nl_query_returns_phase3_error(api_client, upload_id):
    """nl_query is a Phase 1 stub — returns an error message about Phase 3."""
    resp = post_analysis(api_client, upload_id, "nl_query", {"question": "What is the average age?"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "failed"
    assert data["error"] is not None
    assert "Phase 3" in data["error"]


def test_get_analysis_by_id(api_client, upload_id):
    """GET /analyses/{id} returns the stored analysis result."""
    # Create it
    create_resp = post_analysis(api_client, upload_id, "summary_stats")
    assert create_resp.status_code == 200
    analysis_id = create_resp.json()["data"]["analysis_id"]

    # Fetch it
    get_resp = api_client.get(f"/analyses/{analysis_id}")
    assert get_resp.status_code == 200, get_resp.text
    data = get_resp.json()["data"]
    assert data["analysis_id"] == analysis_id
    assert data["status"] == "completed"
    assert data["summary"] and isinstance(data["summary"], str)


def test_get_analysis_not_found(api_client):
    """GET /analyses/{id} returns 404 for unknown id."""
    resp = api_client.get("/analyses/nonexistent-id-xyz")
    assert resp.status_code == 404, resp.text


def test_post_analysis_upload_not_found(api_client):
    """POST /analyses returns 404 when upload_id doesn't exist."""
    resp = api_client.post(
        "/analyses",
        json={"upload_id": "no-such-upload", "analysis_type": "summary_stats", "params": {}},
    )
    assert resp.status_code == 404, resp.text


def test_post_analysis_invalid_type(api_client, upload_id):
    """POST /analyses returns 400 for an unknown analysis_type."""
    resp = api_client.post(
        "/analyses",
        json={"upload_id": upload_id, "analysis_type": "magic_analysis", "params": {}},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"]["code"] == "INVALID_ANALYSIS_TYPE"
