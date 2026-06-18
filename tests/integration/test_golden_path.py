"""Golden-path HTTP smoke test — upload → get session → ask question → get messages."""
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import datachat.db.session as session_module
from datachat.db.models import Base


@pytest.fixture(autouse=True)
def _stub_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATACHAT_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("DATACHAT_GEMINI_API_KEY", "")


@pytest.fixture(autouse=True)
def _use_sqlite(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _reset_llm(monkeypatch):
    import datachat.llm.client as llm_module
    monkeypatch.setattr(llm_module, "_provider", None)
    yield
    monkeypatch.setattr(llm_module, "_provider", None)


@pytest.fixture()
def client():
    from datachat.api import create_app
    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


CSV_CONTENT = b"city,population,area_km2\nParis,2161000,105\nLondon,8982000,1572\nTokyo,13960000,2194\n"


def test_golden_path(client):
    # 1. Health check
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["status"] == "ok"
    assert body["data"]["llm_provider"] == "stub"

    # 2. Upload a CSV
    resp = client.post(
        "/api/sessions",
        files={"file": ("cities.csv", io.BytesIO(CSV_CONTENT), "text/csv")},
    )
    assert resp.status_code == 200
    upload = resp.json()["data"]
    assert upload["status"] == "ready"
    assert upload["row_count"] == 3
    assert "city" in upload["column_names"]
    session_id = upload["session_id"]

    # 3. Get session detail
    resp = client.get(f"/api/sessions/{session_id}")
    assert resp.status_code == 200
    detail = resp.json()["data"]
    assert detail["filename"] == "cities.csv"
    assert detail["status"] == "ready"

    # 4. Ask a question
    resp = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"question": "What is the average population?"},
    )
    assert resp.status_code == 200
    answer_body = resp.json()["data"]
    assert "answer" in answer_body
    assert len(answer_body["answer"]) > 0
    assert isinstance(answer_body["reasoning_trace"], list)
    assert answer_body["llm_provider"] == "stub"

    # 5. Get message history
    resp = client.get(f"/api/sessions/{session_id}/messages")
    assert resp.status_code == 200
    messages = resp.json()["data"]
    assert len(messages) == 2
    roles = [m["role"] for m in messages]
    assert "user" in roles
    assert "assistant" in roles
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "average population" in user_msg["content"]
