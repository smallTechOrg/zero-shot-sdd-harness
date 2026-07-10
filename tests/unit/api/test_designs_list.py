"""GET /api/designs — library listing: order, filter, pagination, params_summary."""

import json


def test_list_designs_empty(api_client):
    r = api_client.get("/api/designs")
    assert r.status_code == 200
    assert r.json()["data"] == {"runs": [], "total": 0}


def test_list_designs_newest_first_with_summary(api_client, make_session_row, make_run_row, utc):
    session_id = make_session_row()
    make_run_row(
        session_id,
        prompt="first",
        status="completed",
        params_json=json.dumps(
            {"clear_span_m": 4.0, "clear_height_m": 3.0, "cushion_m": 2.5, "loading_standard": "25t-2008"}
        ),
        cost_usd=0.02,
        started_at=utc(0),
        duration_ms=30000,
    )
    make_run_row(session_id, prompt="second", status="failed", started_at=utc(60))

    r = api_client.get("/api/designs")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 2
    assert [run["prompt"] for run in data["runs"]] == ["second", "first"]

    newest, oldest = data["runs"]
    assert newest["params_summary"] == ""  # no params extracted on the failed run
    assert oldest["params_summary"] == "4.0 × 3.0 m, cushion 2.5 m, 25t-2008"
    assert oldest["cost_usd"] == 0.02
    assert oldest["duration_ms"] == 30000
    assert oldest["verdict"] is None
    assert set(newest.keys()) == {
        "run_id", "session_id", "prompt", "status", "verdict",
        "params_summary", "cost_usd", "started_at", "duration_ms",
    }


def test_list_designs_session_filter(api_client, make_session_row, make_run_row, utc):
    session_a = make_session_row()
    session_b = make_session_row()
    make_run_row(session_a, prompt="a1", started_at=utc(0))
    make_run_row(session_b, prompt="b1", started_at=utc(10))

    r = api_client.get("/api/designs", params={"session_id": session_a})
    data = r.json()["data"]
    assert data["total"] == 1
    assert data["runs"][0]["prompt"] == "a1"
    assert data["runs"][0]["session_id"] == session_a


def test_list_designs_pagination(api_client, make_session_row, make_run_row, utc):
    session_id = make_session_row()
    for i in range(5):
        make_run_row(session_id, prompt=f"run {i}", started_at=utc(i))

    r = api_client.get("/api/designs", params={"limit": 2, "offset": 1})
    data = r.json()["data"]
    assert data["total"] == 5  # total is unpaginated
    assert [run["prompt"] for run in data["runs"]] == ["run 3", "run 2"]


def test_params_summary_fractional_values(api_client, make_session_row, make_run_row):
    session_id = make_session_row()
    make_run_row(
        session_id,
        params_json=json.dumps(
            {"clear_span_m": 4.25, "clear_height_m": 3.0, "cushion_m": 0.0, "loading_standard": "25t-2008"}
        ),
    )
    r = api_client.get("/api/designs")
    assert r.json()["data"]["runs"][0]["params_summary"] == "4.25 × 3.0 m, cushion 0.0 m, 25t-2008"
