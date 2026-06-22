import pytest


def test_create_session(client):
    resp = client.post("/sessions", json={})
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert "session_id" in data
    assert data["title"] == "New Session"


def test_create_session_with_title(client):
    resp = client.post("/sessions", json={"title": "My Session"})
    assert resp.status_code == 201
    assert resp.json()["data"]["title"] == "My Session"


def test_list_sessions_empty(client):
    resp = client.get("/sessions")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_list_sessions_after_create(client):
    client.post("/sessions", json={"title": "S1"})
    client.post("/sessions", json={"title": "S2"})
    resp = client.get("/sessions")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 2
    titles = {i["title"] for i in items}
    assert "S1" in titles
    assert "S2" in titles


def test_get_session_not_found(client):
    resp = client.get("/sessions/nonexistent-id")
    assert resp.status_code == 404


def test_get_session_detail(client):
    create_resp = client.post("/sessions", json={"title": "Detail Test"})
    session_id = create_resp.json()["data"]["session_id"]
    resp = client.get(f"/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["session_id"] == session_id
    assert data["title"] == "Detail Test"


def test_list_datasets_empty(client):
    create_resp = client.post("/sessions", json={})
    session_id = create_resp.json()["data"]["session_id"]
    resp = client.get(f"/sessions/{session_id}/datasets")
    assert resp.status_code == 200
    assert resp.json()["data"] == []
