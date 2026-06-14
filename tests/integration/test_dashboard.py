"""Dashboard generation and retrieval tests."""
import io
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import datachat.db.session as session_module
import datachat.llm.client as llm_client_module
from datachat.db.models import Base
from datachat.llm.providers.stub import StubLLMProvider

CSV_A = b"month,revenue\nJan,1000\nFeb,1200\nMar,900\n"
CSV_B = b"product,sales\nWidget,500\nGadget,800\n"


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
    return TestClient(create_app(), raise_server_exceptions=True)


def _create_dataset_with_files(client, name="Test DS", files=None):
    files = files or [("a.csv", CSV_A)]
    ds_id = client.post("/api/datasets", json={"name": name}).json()["data"]["id"]
    for fname, content in files:
        r = client.post(
            f"/api/datasets/{ds_id}/uploads",
            files={"file": (fname, io.BytesIO(content), "text/csv")},
        )
        assert r.status_code == 200, r.text
    return ds_id


def test_generate_dashboard_golden_path(client):
    ds_id = _create_dataset_with_files(client, files=[("a.csv", CSV_A), ("b.csv", CSV_B)])

    res = client.post(f"/api/datasets/{ds_id}/dashboard")
    assert res.status_code == 200, res.text
    data = res.json()["data"]

    assert data["dataset_id"] == ds_id
    assert isinstance(data["insights"], list)
    assert len(data["insights"]) >= 1
    assert isinstance(data["charts"], list)
    assert len(data["charts"]) >= 1
    assert "tokens" in data
    assert "cost_usd" in data
    assert "generated_at" in data


def test_get_dashboard_cached(client):
    ds_id = _create_dataset_with_files(client)

    # Generate
    gen_res = client.post(f"/api/datasets/{ds_id}/dashboard")
    assert gen_res.status_code == 200

    # GET returns cached
    get_res = client.get(f"/api/datasets/{ds_id}/dashboard")
    assert get_res.status_code == 200
    assert get_res.json()["data"]["dataset_id"] == ds_id


def test_get_dashboard_not_generated_returns_404(client):
    ds_id = _create_dataset_with_files(client)
    res = client.get(f"/api/datasets/{ds_id}/dashboard")
    assert res.status_code == 404


def test_generate_dashboard_unknown_dataset(client):
    res = client.post("/api/datasets/nonexistent/dashboard")
    assert res.status_code == 404


def test_generate_dashboard_no_files(client):
    ds_id = client.post("/api/datasets", json={"name": "Empty"}).json()["data"]["id"]
    res = client.post(f"/api/datasets/{ds_id}/dashboard")
    assert res.status_code == 400


def test_regenerate_dashboard_replaces_cached(client):
    ds_id = _create_dataset_with_files(client)

    r1 = client.post(f"/api/datasets/{ds_id}/dashboard").json()["data"]
    r2 = client.post(f"/api/datasets/{ds_id}/dashboard").json()["data"]

    # Both should succeed and return insights
    assert len(r1["insights"]) >= 1
    assert len(r2["insights"]) >= 1


def test_stub_dashboard_has_zero_cost(client):
    ds_id = _create_dataset_with_files(client)
    data = client.post(f"/api/datasets/{ds_id}/dashboard").json()["data"]
    assert data["tokens"]["total"] == 0
    assert data["cost_usd"] == 0.0


def test_stub_dashboard_json_is_valid(client):
    ds_id = _create_dataset_with_files(client)
    data = client.post(f"/api/datasets/{ds_id}/dashboard").json()["data"]
    # Stub returns structured insights + charts
    assert all(isinstance(s, str) for s in data["insights"])
    assert all(isinstance(c, dict) for c in data["charts"])
    for chart in data["charts"]:
        assert "type" in chart
        assert "title" in chart
