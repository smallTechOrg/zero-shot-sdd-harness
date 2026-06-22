import io

import pytest
from fastapi.testclient import TestClient

from data_analyst.api import create_app


@pytest.fixture()
def client():
    return TestClient(create_app())


def test_health_reports_stub_without_key(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["llm_provider"] == "stub"


def test_golden_path_full_user_journey(client):
    # 1. Home page renders and shows the stub banner.
    home = client.get("/")
    assert home.status_code == 200
    assert "STUB MODE" in home.text
    assert "Senior Data Analyst Agent" in home.text

    # 2. Create a session.
    created = client.post("/sessions", json={"name": "Q2 review"})
    assert created.status_code == 200
    session_id = created.json()["id"]

    # 3. Upload a CSV dataset.
    csv = b"region,sales\nNorth,100\nSouth,250\nNorth,50\n"
    up = client.post(
        f"/sessions/{session_id}/datasets",
        files={"file": ("sales.csv", io.BytesIO(csv), "text/csv")},
        data={"name": "sales"},
    )
    assert up.status_code == 200, up.text
    assert up.json()["row_count"] == 3
    assert any(c["name"] == "region" for c in up.json()["schema"])

    # 4. List datasets — content assertion, not just status.
    listed = client.get(f"/sessions/{session_id}/datasets")
    assert listed.status_code == 200
    assert listed.json()["datasets"][0]["name"] == "sales"

    # 5. Ask a question — agent runs end-to-end on the stub.
    asked = client.post(
        f"/sessions/{session_id}/ask",
        json={"question": "how many sales rows are there?"},
    )
    assert asked.status_code == 200, asked.text
    payload = asked.json()
    assert payload["answer_text"]
    assert payload["generated_sql"]
    assert payload["status"] == "completed"

    # 6. Audit log records the operation.
    audit = client.get(f"/sessions/{session_id}/audit")
    assert audit.status_code == 200
    entries = audit.json()["entries"]
    assert any(e["status"] == "success" for e in entries)

    # 7. Session page renders the conversation + audit content.
    page = client.get(f"/sessions/{session_id}")
    assert page.status_code == 200
    assert "sales" in page.text
    assert "Audit log" in page.text
