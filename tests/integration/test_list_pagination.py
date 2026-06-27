"""Integration tests for the AJAX-loaded list surfaces:

- the relocated HTML-fragment endpoints (GET /databases, /sessions, /sessions/{id}/queries) with keyset
  cursors carried in ``X-Next-Cursor``;
- the ``_meta`` enrichment the management UI reads off the MCP JSON-RPC ``*/list`` responses.

All in stub mode against a tmp SQLite DB, with ``ui_page_size`` forced to 2 so paging is exercised.
"""
import csv
import io

import pytest
from fastapi.testclient import TestClient

import data_analysis_agent.db.session as session_module
from data_analysis_agent.db.database import Database
from data_analysis_agent.db.models import (
    DatabaseRow,
    QueryRecordRow,
    SessionDatabaseRow,
    SessionRow,
)


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAANALYSIS_OPENROUTER_API_KEY", "")
    monkeypatch.setenv("DATAANALYSIS_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DATAANALYSIS_DATASETS_DIR", str(tmp_path / "datasets"))
    monkeypatch.setenv("DATAANALYSIS_CHECKPOINT_DB", str(tmp_path / "ckpt.db"))
    monkeypatch.setenv("DATAANALYSIS_UI_PAGE_SIZE", "2")   # tiny pages so Prev/Next has work to do
    db = Database(f"sqlite:///{tmp_path / 'app.db'}")
    db._init_schema()
    monkeypatch.setattr(session_module, "_db", db)
    monkeypatch.setattr(session_module, "init_db", lambda: None)
    yield
    db._dispose()
    monkeypatch.setattr(session_module, "_db", None)


@pytest.fixture
def client():
    import data_analysis_agent.llm.client as llm_module
    llm_module._client = None
    from data_analysis_agent.api import create_app
    with TestClient(create_app(), raise_server_exceptions=True) as c:
        yield c


def _orders() -> bytes:
    buf = io.StringIO()
    csv.writer(buf).writerows([["id", "amount"], [1, 5], [2, 7]])
    return buf.getvalue().encode()


def _make_database(client, name: str) -> str:
    up = client.post("/database/upload", data={"database_name": name},
                     files={"file": ("orders.csv", _orders(), "text/csv")})
    assert up.status_code == 200, up.text
    r = client.post("/database", data={"name": name, "database_type": "parquet", "database_uri": up.json()["uri"]},
                    follow_redirects=True)
    assert r.status_code == 200
    with session_module.create_db_session() as db:
        return db.query(DatabaseRow).filter(DatabaseRow.name == name).one().id


def _seed_sessions(database_id: str, n: int) -> list[str]:
    ids = []
    with session_module.create_db_session() as db:
        for i in range(n):
            row = SessionRow(name=f"S{i}")
            db.add(row)
            db.flush()
            db.add(SessionDatabaseRow(session_id=row.id, database_id=database_id))
            ids.append(row.id)
    return ids


def _seed_queries(session_id: str, n: int) -> None:
    with session_module.create_db_session() as db:
        for i in range(n):
            db.add(QueryRecordRow(session_id=session_id, question=f"Q{i}", status="completed", answer=f"A{i}"))


# --- relocated HTML-fragment endpoints (cursor + X-Next-Cursor) --------------

def test_databases_fragment_paginates(client):
    for name in ("alpha", "beta", "gamma"):
        _make_database(client, name)
    p1 = client.get("/databases")
    assert p1.status_code == 200
    assert p1.text.count("srv-row") == 2                 # page size 2
    cursor = p1.headers.get("X-Next-Cursor")
    assert cursor                                        # a third database remains
    p2 = client.get("/databases", params={"cursor": cursor})
    assert p2.text.count("srv-row") == 1
    assert "X-Next-Cursor" not in p2.headers             # exhausted


def test_sessions_fragment_paginates_and_marks_active(client):
    db_id = _make_database(client, "db")
    ids = _seed_sessions(db_id, 3)
    p1 = client.get("/sessions", params={"active": ids[0]})
    assert p1.status_code == 200
    assert p1.text.count("session-item") == 2
    assert p1.headers.get("X-Next-Cursor")
    # the active session (most-recently-updated last → may be on a later page); fetch all and check the class
    seen = p1.text
    seen += client.get("/sessions", params={"cursor": p1.headers["X-Next-Cursor"], "active": ids[0]}).text
    assert "session-item active" in seen


def test_queries_fragment_paginates(client):
    db_id = _make_database(client, "db")
    sess_id = _seed_sessions(db_id, 1)[0]
    _seed_queries(sess_id, 3)
    p1 = client.get(f"/sessions/{sess_id}/queries")
    assert p1.status_code == 200
    assert p1.text.count('id="q-') == 2                  # one turn container per record
    assert p1.headers.get("X-Next-Cursor")
    p2 = client.get(f"/sessions/{sess_id}/queries", params={"cursor": p1.headers["X-Next-Cursor"]})
    assert p2.text.count('id="q-') == 1
    assert "X-Next-Cursor" not in p2.headers


def test_invalid_cursor_is_400(client):
    _make_database(client, "db")
    r = client.get("/databases", params={"cursor": "not-a-real-cursor"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_CURSOR"


# --- _meta enrichment on the JSON-RPC list surface ---------------------------

def _rpc(client, database_id, method):
    return client.post(f"/database/{database_id}",
                       json={"jsonrpc": "2.0", "id": 1, "method": method}).json()["result"]


def test_list_methods_carry_meta_for_the_ui(client):
    database_id = _make_database(client, "db")
    tool = _rpc(client, database_id, "tools/list")["tools"][0]
    assert "sql_template" in tool["_meta"]["execution"]   # editor payload, not in the public inputSchema

    resources = _rpc(client, database_id, "resources/list")["resources"]
    assert all("kind" in r["_meta"] for r in resources)   # drives the kind pill + edit branch
    assert any(r["_meta"]["kind"] == "schema" for r in resources)

    prompts = _rpc(client, database_id, "prompts/list")["prompts"]
    assert all("template" in p["_meta"] for p in prompts)
