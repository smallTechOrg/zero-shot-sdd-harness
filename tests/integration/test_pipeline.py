"""Golden-path smoke test: upload CSV → ask question → get answer."""
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import datachat.db.session as session_module
import datachat.llm.client as llm_client_module
from datachat.db.models import Base
from datachat.llm.providers.stub import StubLLMProvider


CSV_CONTENT = b"name,age,city\nAlice,30,NYC\nBob,25,LA\nCarol,35,Chicago\n"


@pytest.fixture(autouse=True)
def _use_sqlite_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _use_stub_llm(monkeypatch):
    stub = StubLLMProvider()
    monkeypatch.setattr(llm_client_module, "_provider", stub)
    monkeypatch.setattr(llm_client_module, "_is_stub", True)


@pytest.fixture(autouse=True)
def _use_tmp_upload_dir(tmp_path, monkeypatch):
    import datachat.config.settings as settings_mod
    from datachat.config.settings import Settings
    monkeypatch.setattr(
        settings_mod, "_settings",
        Settings(database_url=f"sqlite:///{tmp_path}/test.db", upload_dir=str(tmp_path / "uploads")),
    )
    (tmp_path / "uploads").mkdir()


@pytest.fixture
def client():
    from datachat.api.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=True)


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_index_renders_stub_banner(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Stub Mode" in res.text
    assert "DataChat" in res.text


def test_golden_path_upload_and_query(client):
    # Upload CSV
    res = client.post(
        "/api/uploads",
        files={"file": ("data.csv", io.BytesIO(CSV_CONTENT), "text/csv")},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["original_filename"] == "data.csv"
    assert data["row_count"] == 3
    assert "name" in data["columns"]
    assert "age" in data["columns"]
    upload_id = data["id"]

    # Fetch upload by id
    res2 = client.get(f"/api/uploads/{upload_id}")
    assert res2.status_code == 200
    assert res2.json()["data"]["id"] == upload_id

    # Ask a question
    res3 = client.post(
        "/api/queries",
        json={"upload_id": upload_id, "question": "What is the average age?"},
    )
    assert res3.status_code == 200, res3.text
    q_data = res3.json()["data"]
    assert q_data["upload_id"] == upload_id
    assert "age" in q_data["question"]
    assert len(q_data["answer"]) > 0
    query_id = q_data["id"]

    # Fetch query by id
    res4 = client.get(f"/api/queries/{query_id}")
    assert res4.status_code == 200
    assert res4.json()["data"]["id"] == query_id


def test_upload_rejects_non_csv(client):
    res = client.post(
        "/api/uploads",
        files={"file": ("data.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert res.status_code == 400


def test_query_unknown_upload(client):
    res = client.post(
        "/api/queries",
        json={"upload_id": "nonexistent-id", "question": "What?"},
    )
    assert res.status_code == 404
