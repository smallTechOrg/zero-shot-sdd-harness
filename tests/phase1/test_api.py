"""API + golden-path E2E tests for the data-analysis agent.

Runs against the real Gemini API (key from .env) and a real isolated SQLite DB
(the conftest ``_isolated_db`` fixture). The mandatory test is the full primary
journey: upload a CSV → ask a question over SSE → assert the streamed answer
carries prose + chart + table + code + tokens + cost + daily total.
"""
import io
import json

import pytest


# --- helpers ----------------------------------------------------------------


def _csv_bytes() -> bytes:
    rows = ["region,amount"]
    # Four regions with clearly different totals → a groupby is the obvious plan.
    data = {"north": [10, 20, 30], "south": [5, 5, 5], "east": [100], "west": [1, 2]}
    for region, amounts in data.items():
        for a in amounts:
            rows.append(f"{region},{a}")
    return ("\n".join(rows) + "\n").encode()


def _upload(client, name="sales.csv") -> dict:
    resp = client.post(
        "/datasets",
        files={"file": (name, io.BytesIO(_csv_bytes()), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _parse_sse(raw_text: str) -> list[dict]:
    """Parse a text/event-stream body into [{event, data(dict)}]."""
    events: list[dict] = []
    event_name = None
    data_lines: list[str] = []
    for line in raw_text.splitlines():
        if line.startswith("event:"):
            event_name = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].strip())
        elif line == "":
            if event_name is not None:
                payload = "\n".join(data_lines)
                try:
                    data = json.loads(payload) if payload else {}
                except json.JSONDecodeError:
                    data = {"_raw": payload}
                events.append({"event": event_name, "data": data})
            event_name = None
            data_lines = []
    # Flush a trailing event with no terminating blank line.
    if event_name is not None:
        payload = "\n".join(data_lines)
        data = json.loads(payload) if payload else {}
        events.append({"event": event_name, "data": data})
    return events


def _ask(client, dataset_id: str, question: str) -> list[dict]:
    with client.stream(
        "POST", f"/datasets/{dataset_id}/ask", json={"question": question}
    ) as resp:
        assert resp.status_code == 200, resp.read()
        body = b"".join(resp.iter_bytes()).decode()
    return _parse_sse(body)


# --- upload -----------------------------------------------------------------


def test_upload_returns_profile_without_raw_rows(api_client):
    data = _upload(api_client)
    assert data["dataset_id"]
    assert data["name"] == "sales.csv"
    assert data["row_count"] == 9
    assert data["col_count"] == 2
    profile = data["profile"]
    assert "columns" in profile and profile["columns"]
    # Privacy: no raw cell values (e.g. the region strings) leak into the profile.
    blob = json.dumps(profile)
    assert "north" not in blob and "100" not in blob.replace('"max": 100', "")


def test_upload_rejects_non_tabular(api_client):
    resp = api_client.post(
        "/datasets",
        files={"file": ("notes.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    assert resp.status_code == 400


# --- golden-path E2E (real LLM) --------------------------------------------


@pytest.mark.usefixtures("_require_llm_key")
def test_golden_path_upload_ask_stream(api_client):
    data = _upload(api_client)
    dataset_id = data["dataset_id"]

    events = _ask(api_client, dataset_id, "What is the total amount by region?")
    names = [e["event"] for e in events]

    assert "run_started" in names, names
    assert names.count("step") >= 1, names
    assert "answer" in names, names

    run_started = next(e for e in events if e["event"] == "run_started")
    assert run_started["data"]["run_id"]
    assert run_started["data"]["max_steps"] >= 1

    answer = next(e for e in events if e["event"] == "answer")["data"]
    assert answer.get("status") == "completed", answer
    assert isinstance(answer.get("prose"), str) and answer["prose"].strip(), answer
    assert answer.get("code"), "final code missing"
    assert answer.get("table") and answer["table"].get("columns"), answer
    assert answer["table"].get("rows"), answer

    # Chart adapted to the frontend contract: {type, x, y, data}.
    chart = answer.get("chart")
    assert chart is not None, "no chart spec"
    assert "type" in chart and "x" in chart and "y" in chart and "data" in chart, chart

    # Cost / token meters present and forwarded.
    tokens = answer.get("tokens")
    assert tokens and tokens.get("prompt", 0) > 0, tokens
    assert "cost_usd" in answer
    assert "daily_total_usd" in answer
    assert "uncertainty" in answer

    assert "done" in names, names


# --- history / detail / usage ----------------------------------------------


@pytest.mark.usefixtures("_require_llm_key")
def test_history_detail_and_usage(api_client):
    data = _upload(api_client)
    dataset_id = data["dataset_id"]
    events = _ask(api_client, dataset_id, "What is the total amount by region?")
    run_id = next(e for e in events if e["event"] == "run_started")["data"]["run_id"]

    # Per-dataset run list.
    runs = api_client.get(f"/datasets/{dataset_id}/runs").json()["data"]["runs"]
    assert any(r["run_id"] == run_id for r in runs), runs
    listed = next(r for r in runs if r["run_id"] == run_id)
    assert listed["status"] == "completed"
    assert listed["step_count"] >= 1

    # Full run detail with steps.
    detail = api_client.get(f"/runs/{run_id}").json()["data"]
    assert detail["run_id"] == run_id
    assert detail["steps"], "no steps recorded"
    assert detail["prose"]
    assert detail["final_code"]

    # Daily usage meter.
    usage = api_client.get("/usage/today").json()["data"]
    assert usage["run_count"] >= 1
    assert usage["total_cost_usd"] >= 0.0
    assert usage["total_tokens"] >= 0


# --- error cases ------------------------------------------------------------


def test_ask_unknown_dataset_404(api_client):
    resp = api_client.post("/datasets/does-not-exist/ask", json={"question": "hi"})
    assert resp.status_code == 404


def test_ask_empty_question_400(api_client):
    data = _upload(api_client)
    resp = api_client.post(f"/datasets/{data['dataset_id']}/ask", json={"question": "   "})
    assert resp.status_code == 400


def test_phase2_list_datasets_is_labelled_stub(api_client):
    resp = api_client.get("/datasets")
    assert resp.status_code == 501
    assert "Phase 2" in resp.json()["detail"]["message"]
