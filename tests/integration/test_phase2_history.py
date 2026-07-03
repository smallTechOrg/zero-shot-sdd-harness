"""Phase-2 run-history test — REAL Gemini via .env, production driver.

Asks two questions, then exercises the history surfaces: list (newest-first),
detail (identical to creation), and re-run (a NEW run row that leaves the
original untouched).

Skips (never stubs) when no Gemini key is present.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("_require_llm_key")

_CSV = "region,amount\nNorth,100\nSouth,40\nEast,20\n"


def _upload(api_client) -> dict:
    r = api_client.post(
        "/datasets",
        files={"file": ("mini.csv", _CSV.encode(), "text/csv")},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _ask(api_client, dataset_id: str, question: str) -> dict:
    r = api_client.post("/runs", json={"dataset_id": dataset_id, "question": question})
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["status"] == "completed", f"run failed: {body.get('error')}"
    return body


def test_history_list_detail_and_rerun(api_client):
    ds = _upload(api_client)

    b1 = _ask(api_client, ds["id"], "What is the total amount?")
    b2 = _ask(api_client, ds["id"], "What is the total amount by region?")

    # The runner rolls token/cost usage up onto the run row.
    assert b1["tokens_used"] and b1["tokens_used"] > 0, "tokens_used not recorded"
    assert b1["cost_estimate_usd"] is not None and b1["cost_estimate_usd"] >= 0
    assert b1["created_at"]

    # List — newest-first, with the summary fields.
    lr = api_client.get(f"/runs?dataset_id={ds['id']}")
    assert lr.status_code == 200, lr.text
    listed = lr.json()["data"]
    assert len(listed) == 2
    assert listed[0]["run_id"] == b2["run_id"], "history is not newest-first"
    assert listed[1]["run_id"] == b1["run_id"]
    for item in listed:
        assert item["question"]
        assert item["status"] == "completed"
        assert item["created_at"]

    # Detail — identical to what creation returned.
    dr = api_client.get(f"/runs/{b1['run_id']}")
    assert dr.status_code == 200, dr.text
    detail = dr.json()["data"]
    assert detail["answer_text"] == b1["answer_text"]
    assert detail["code"] == b1["code"]
    assert detail["table"] == b1["table"]
    assert detail["chart"] == b1["chart"]

    # Re-run — a NEW run id; the original stays untouched.
    rr = api_client.post(f"/runs/{b1['run_id']}/rerun")
    assert rr.status_code == 200, rr.text
    new_run = rr.json()["data"]
    assert new_run["run_id"] != b1["run_id"]
    assert new_run["status"] == "completed", f"rerun failed: {new_run.get('error')}"
    assert new_run["dataset_id"] == ds["id"]

    orig = api_client.get(f"/runs/{b1['run_id']}").json()["data"]
    assert orig["answer_text"] == b1["answer_text"]
    assert orig["code"] == b1["code"]
    assert orig["table"] == b1["table"]

    # There are now three runs for the dataset (2 asked + 1 re-run).
    all_runs = api_client.get(f"/runs?dataset_id={ds['id']}").json()["data"]
    assert len(all_runs) == 3


def test_rerun_unknown_run_returns_404(api_client):
    r = api_client.post("/runs/does-not-exist/rerun")
    assert r.status_code == 404


def test_get_unknown_run_returns_404(api_client):
    r = api_client.get("/runs/does-not-exist")
    assert r.status_code == 404


def test_list_runs_empty_dataset_returns_empty(api_client):
    ds = _upload(api_client)
    r = api_client.get(f"/runs?dataset_id={ds['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["data"] == []
