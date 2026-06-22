"""
End-to-end golden path tests for the Data Analyst Agent.
These tests exercise the full stack: upload → chat → history → summarisation.
All Gemini calls are real (live API key from .env).
"""
import io
import json
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load .env so GEMINI_API_KEY is in os.environ for all tests in this file
load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture()
def e2e_client(tmp_path, monkeypatch):
    """Full isolated app client for E2E tests."""
    db_path = tmp_path / "e2e.db"
    duckdb_path = tmp_path / "e2e.duckdb"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.setenv("DA_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DA_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("DA_UPLOAD_DIR", str(upload_dir))

    import data_analyst.config.settings as settings_mod
    import data_analyst.db.session as session_mod
    import data_analyst.duckdb_service as duckdb_mod

    settings_mod._settings = None
    session_mod._engine = None
    session_mod._SessionLocal = None
    duckdb_mod._duckdb_service = None

    from data_analyst.api import create_app
    from fastapi.testclient import TestClient
    app = create_app()

    with TestClient(app) as client:
        yield client

    settings_mod._settings = None
    session_mod._engine = None
    session_mod._SessionLocal = None
    duckdb_mod._duckdb_service = None


@pytest.fixture()
def sample_csv_path():
    return Path(__file__).parent.parent / "fixtures" / "sample.csv"


# ─── UI smoke test ────────────────────────────────────────────────────────────

def test_ui_serves_spa(e2e_client):
    """GET / must return 200 with the SPA HTML containing required elements."""
    r = e2e_client.get("/")
    assert r.status_code == 200
    text = r.text
    assert "<title>Data Analyst Agent</title>" in text
    assert 'id="upload-btn"' in text
    assert 'id="chat-messages"' in text


# ─── Health check ─────────────────────────────────────────────────────────────

def test_health_check(e2e_client):
    """GET /health must return 200 with status ok."""
    r = e2e_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


# ─── Golden path: upload → 3 questions → history ─────────────────────────────

def test_golden_path_upload_and_chat(e2e_client, sample_csv_path):
    """
    Full golden path:
    1. Upload sample.csv
    2. Ask 3 sequential questions
    3. Verify each response is non-empty markdown
    4. Verify session history contains all turns
    5. Verify audit log has 3+ entries
    """
    # Step 1: Upload
    with open(sample_csv_path, "rb") as f:
        r = e2e_client.post(
            "/datasets",
            files={"file": ("sample.csv", f, "text/csv")},
            data={"name": "employees"},
        )
    assert r.status_code == 201
    dataset_id = r.json()["dataset_id"]
    assert dataset_id is not None

    # Step 2: First question
    r1 = e2e_client.post(
        "/chat",
        json={"message": "How many employees are there in total?"},
    )
    assert r1.status_code == 200
    b1 = r1.json()
    session_id = b1["session_id"]
    assert len(b1["response_markdown"]) > 0
    assert b1["latency_ms"] > 0

    # Step 3: Second question (with session)
    r2 = e2e_client.post(
        "/chat",
        json={"session_id": session_id, "message": "What is the average salary by department?"},
    )
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["session_id"] == session_id
    assert len(b2["response_markdown"]) > 0

    # Step 4: Third question (with session)
    r3 = e2e_client.post(
        "/chat",
        json={"session_id": session_id, "message": "Who is the highest paid employee?"},
    )
    assert r3.status_code == 200
    b3 = r3.json()
    assert b3["session_id"] == session_id
    assert len(b3["response_markdown"]) > 0

    # Step 5: Verify session history
    hist_r = e2e_client.get(f"/sessions/{session_id}/history")
    assert hist_r.status_code == 200
    hist = hist_r.json()
    turns = hist["turns"]
    assert len(turns) >= 6  # 3 user + 3 assistant turns

    user_turns = [t for t in turns if t["role"] == "user"]
    assert len(user_turns) >= 3

    # Step 6: Verify audit log entries
    import data_analyst.db.session as session_mod
    from data_analyst.db.models import AuditLog
    factory = session_mod._SessionLocal
    with factory() as db:
        logs = db.query(AuditLog).filter(AuditLog.session_id == session_id).all()
        assert len(logs) >= 3, f"Expected >=3 audit log entries, got {len(logs)}"


# ─── Server restart simulation ────────────────────────────────────────────────

def test_session_survives_server_restart(tmp_path, monkeypatch, sample_csv_path):
    """
    Simulate server restart: create a session, then recreate the app from scratch
    (resetting all singletons), then verify the session history is still accessible.
    """
    db_path = tmp_path / "persist.db"
    duckdb_path = tmp_path / "persist.duckdb"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.setenv("DA_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DA_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("DA_UPLOAD_DIR", str(upload_dir))

    import data_analyst.config.settings as settings_mod
    import data_analyst.db.session as session_mod
    import data_analyst.duckdb_service as duckdb_mod
    from data_analyst.api import create_app
    from fastapi.testclient import TestClient

    def reset_singletons():
        settings_mod._settings = None
        session_mod._engine = None
        session_mod._SessionLocal = None
        duckdb_mod._duckdb_service = None

    # First server boot
    reset_singletons()
    app1 = create_app()
    with TestClient(app1) as c1:
        with open(sample_csv_path, "rb") as f:
            r = c1.post(
                "/datasets",
                files={"file": ("sample.csv", f, "text/csv")},
                data={"name": "employees"},
            )
        assert r.status_code == 201

        chat_r = c1.post(
            "/chat",
            json={"message": "How many rows are there?"},
        )
        assert chat_r.status_code == 200
        session_id = chat_r.json()["session_id"]

    # Simulate restart — reset all in-memory state
    reset_singletons()

    # Second server boot (same DB path)
    app2 = create_app()
    with TestClient(app2) as c2:
        # History must still be accessible
        hist_r = c2.get(f"/sessions/{session_id}/history")
        assert hist_r.status_code == 200
        turns = hist_r.json()["turns"]
        assert len(turns) >= 2

        # DuckDB tables must be re-registered — can continue chat
        chat_r2 = c2.post(
            "/chat",
            json={"session_id": session_id, "message": "What is the maximum salary?"},
        )
        assert chat_r2.status_code == 200
        assert chat_r2.json()["session_id"] == session_id


# ─── Token economy: summarisation ────────────────────────────────────────────

def test_summarisation_triggered_when_turns_exceed_max(tmp_path, monkeypatch, sample_csv_path):
    """
    Insert >max_history_turns turns directly into the DB, then call _maybe_summarise.
    Verify session.summary is set and some turns are marked is_summarised=True.
    """
    db_path = tmp_path / "summary.db"
    duckdb_path = tmp_path / "summary.duckdb"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.setenv("DA_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DA_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("DA_UPLOAD_DIR", str(upload_dir))
    # Low threshold to trigger summarisation easily
    monkeypatch.setenv("DA_MAX_HISTORY_TURNS", "6")
    monkeypatch.setenv("DA_SUMMARY_KEEP_TURNS", "2")

    import data_analyst.config.settings as settings_mod
    import data_analyst.db.session as session_mod
    import data_analyst.duckdb_service as duckdb_mod

    settings_mod._settings = None
    session_mod._engine = None
    session_mod._SessionLocal = None
    duckdb_mod._duckdb_service = None

    from data_analyst.db.session import init_db, _get_session_factory
    init_db()
    factory = _get_session_factory()  # initialises _SessionLocal

    from data_analyst.db.models import Session as SessionModel, ConversationTurn
    from data_analyst.agent.runner import _maybe_summarise

    # Create a session and 10 turns (> MAX_HISTORY_TURNS=6)
    with factory() as db:
        s = SessionModel()
        db.add(s)
        db.flush()
        session_id = s.id

        for i in range(10):
            role = "user" if i % 2 == 0 else "assistant"
            db.add(ConversationTurn(
                session_id=session_id,
                role=role,
                content=f"Turn {i}: {'What is the average salary?' if role == 'user' else 'The average salary is $80,000.'}",
                turn_index=i,
            ))
        db.commit()

    # Call _maybe_summarise directly
    settings = settings_mod.get_settings()
    with factory() as db:
        _maybe_summarise(db, session_id, settings)
        db.commit()

    # Verify summary was set and turns were marked
    with factory() as db:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        assert session.summary is not None, "Summary should have been set"
        assert len(session.summary) > 10, "Summary should be non-trivial"

        summarised = db.query(ConversationTurn).filter(
            ConversationTurn.session_id == session_id,
            ConversationTurn.is_summarised == True,  # noqa: E712
        ).count()
        assert summarised > 0, "At least some turns should be marked as summarised"

        not_summarised = db.query(ConversationTurn).filter(
            ConversationTurn.session_id == session_id,
            ConversationTurn.is_summarised == False,  # noqa: E712
        ).count()
        # Summary keep turns should remain
        assert not_summarised <= settings.summary_keep_turns


# ─── Edge cases ───────────────────────────────────────────────────────────────

def test_empty_file_upload_then_chat(e2e_client):
    """Upload CSV with 0 data rows, then ask about it — agent responds gracefully."""
    csv_content = b"col_a,col_b\n"
    r = e2e_client.post(
        "/datasets",
        files={"file": ("empty.csv", io.BytesIO(csv_content), "text/csv")},
        data={"name": "empty_ds"},
    )
    assert r.status_code == 201
    assert r.json()["row_count"] == 0

    chat_r = e2e_client.post(
        "/chat",
        json={"message": "What is in the empty_ds table?"},
    )
    assert chat_r.status_code == 200
    # Agent must respond — not crash
    assert len(chat_r.json()["response_markdown"]) > 0


def test_malformed_csv_upload_rejected(e2e_client):
    """Malformed CSV (mismatched columns) returns 422."""
    # CSV with inconsistent column counts — pandas raises a tokenization error
    malformed = b"a,b,c\n1,2\n3,4,5,6,7\n8,9"
    r = e2e_client.post(
        "/datasets",
        files={"file": ("bad.csv", io.BytesIO(malformed), "text/csv")},
        data={"name": "bad"},
    )
    assert r.status_code == 422


def test_empty_message_rejected(e2e_client):
    """POST /chat with empty message returns 422."""
    r = e2e_client.post("/chat", json={"message": ""})
    assert r.status_code == 422


def test_health_endpoint(e2e_client):
    """GET /health returns 200 and includes required fields."""
    r = e2e_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert body["status"] == "ok"
