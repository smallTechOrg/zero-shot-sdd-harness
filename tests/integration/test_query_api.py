import io
import json
import pytest

CSV_CONTENT = b"name,value\nAlice,10\nBob,20\nCarol,30\n"


def _create_session_with_dataset(client):
    resp = client.post("/sessions", json={})
    sid = resp.json()["data"]["session_id"]
    client.post(
        f"/sessions/{sid}/upload",
        files={"file": ("data.csv", io.BytesIO(CSV_CONTENT), "text/csv")},
    )
    return sid


def test_query_happy_path_stub(client, monkeypatch):
    """With stub LLM (no API key), should return 200 with sql, results, answer."""
    sid = _create_session_with_dataset(client)
    resp = client.post(
        f"/sessions/{sid}/query",
        json={"question": "how many rows are there?"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "sql" in data
    assert "results" in data
    assert "answer" in data
    assert "token_usage" in data
    assert isinstance(data["results"], list)


def test_query_no_datasets(client):
    resp = client.post("/sessions", json={})
    sid = resp.json()["data"]["session_id"]
    resp = client.post(f"/sessions/{sid}/query", json={"question": "test?"})
    assert resp.status_code == 400
    assert "no_datasets" in resp.json()["detail"]["code"]


def test_query_session_not_found(client):
    resp = client.post("/sessions/nonexistent/query", json={"question": "test?"})
    assert resp.status_code == 404


def test_query_token_budget_exceeded(client, monkeypatch):
    import data_analyst.api.query as query_module
    monkeypatch.setattr(query_module, "check_budget", lambda prompt, hard_cap: (False, 99999))
    sid = _create_session_with_dataset(client)
    resp = client.post(f"/sessions/{sid}/query", json={"question": "test?"})
    assert resp.status_code == 422
    assert "token_budget_exceeded" in resp.json()["detail"]["code"]


def test_query_invalid_sql(client, monkeypatch):
    import data_analyst.api.query as query_module

    def _raise_value_error(x):
        raise ValueError("Unsafe SQL")

    monkeypatch.setattr(query_module, "extract_sql", _raise_value_error)
    sid = _create_session_with_dataset(client)
    resp = client.post(f"/sessions/{sid}/query", json={"question": "test?"})
    assert resp.status_code == 422
