"""Phase-2 conversation-sessions test — REAL Gemini via .env, production driver.

Proves conversation memory threading: a follow-up question that CANNOT be
answered without the prior turn ("now just the region with the highest total")
resolves to the correct top region only because the first turn is in context.

Skips (never stubs) when no Gemini key is present.
"""
from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.usefixtures("_require_llm_key")

# North total = 150 (top), South = 15, East = 3 → the highest region is North.
_CSV = "region,amount\nNorth,100\nNorth,50\nSouth,10\nSouth,5\nEast,3\n"
_TOP_REGION = "North"


def _upload(api_client) -> dict:
    r = api_client.post(
        "/datasets",
        files={"file": ("mini.csv", _CSV.encode(), "text/csv")},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_follow_up_uses_prior_turn(api_client):
    ds = _upload(api_client)

    sr = api_client.post("/sessions", json={"dataset_id": ds["id"]})
    assert sr.status_code == 200, sr.text
    session = sr.json()["data"]
    session_id = session["id"]
    assert session["dataset_id"] == ds["id"]
    assert session["runs"] == []

    # Q1 — establishes the per-region totals in the conversation.
    r1 = api_client.post(
        "/runs",
        json={
            "dataset_id": ds["id"],
            "question": "What is the total amount by region?",
            "session_id": session_id,
        },
    )
    assert r1.status_code == 200, r1.text
    b1 = r1.json()["data"]
    assert b1["status"] == "completed", f"Q1 failed: {b1.get('error')}"
    assert b1["session_id"] == session_id

    # Q2 — a context-only follow-up: it names no region and can only be answered
    # by carrying Q1's result forward.
    r2 = api_client.post(
        "/runs",
        json={
            "dataset_id": ds["id"],
            "question": "Now show only the region with the highest total.",
            "session_id": session_id,
        },
    )
    assert r2.status_code == 200, r2.text
    b2 = r2.json()["data"]
    assert b2["status"] == "completed", f"Q2 failed: {b2.get('error')}"
    assert b2["session_id"] == session_id

    # The follow-up must resolve to the true top region (North).
    haystack = (b2["answer_text"] or "") + json.dumps(b2["table"], default=str)
    assert _TOP_REGION in haystack, (
        f"follow-up did not resolve to the top region '{_TOP_REGION}': "
        f"answer={b2.get('answer_text')!r} table={b2.get('table')}"
    )

    # Both runs are linked to the same session.
    lr = api_client.get(f"/runs?session_id={session_id}")
    assert lr.status_code == 200, lr.text
    listed = lr.json()["data"]
    assert len(listed) == 2, listed
    assert {row["run_id"] for row in listed} == {b1["run_id"], b2["run_id"]}

    # GET /sessions/{id} returns both turns, newest-first.
    gs = api_client.get(f"/sessions/{session_id}")
    assert gs.status_code == 200, gs.text
    sruns = gs.json()["data"]["runs"]
    assert len(sruns) == 2
    assert sruns[0]["run_id"] == b2["run_id"]


def test_create_session_unknown_dataset_returns_404(api_client):
    r = api_client.post("/sessions", json={"dataset_id": "does-not-exist"})
    assert r.status_code == 404


def test_get_unknown_session_returns_404(api_client):
    r = api_client.get("/sessions/does-not-exist")
    assert r.status_code == 404
