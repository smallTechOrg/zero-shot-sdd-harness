"""Full real-path integration tests against the REAL Gemini API.

Skipped if no LLM key is set (per the boilerplate fixture). These drive the
whole upload -> ask -> plan -> generate_code -> execute_code -> finalize loop
over the FULL olist CSV and assert on real content.
"""
import io
import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from db.models import DatasetRow, RunRow
import db.session as session_module
from analyst.profile import profile_csv
from graph.runner import run_agent

OLIST = (
    Path(__file__).resolve().parent.parent.parent
    / "src" / "data" / "datasets"
    / "8bc76e9e-1151-437e-95eb-727b57b674ee"
    / "olist_orders_dataset.csv"
)
QUESTION = "How many orders are there for each order_status?"


def _seed_dataset(engine, path: Path) -> str:
    prof = profile_csv(str(path))
    with Session(engine) as s:
        ds = DatasetRow(
            filename=path.name,
            path=str(path),
            row_count=prof.row_count,
            schema_json=json.dumps(prof.schema),
            sample_json=json.dumps(prof.sample_rows),
        )
        s.add(ds)
        s.commit()
        return ds.id


@pytest.mark.usefixtures("_require_llm_key")
def test_full_analysis_real_gemini(_isolated_db):
    """Happy path: real Gemini writes pandas, it runs over the full file, and we
    get a completed run with an answer + chart + table + audit trail."""
    assert OLIST.exists(), f"sample CSV missing at {OLIST}"
    dataset_id = _seed_dataset(_isolated_db, OLIST)

    run_id = run_agent(dataset_id, QUESTION)

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)

    assert run is not None
    assert run.status == "completed", f"expected completed, got {run.status}: {run.error_message}"
    assert run.answer and len(run.answer) > 10
    assert run.chart_spec_json, "expected a chart spec"
    chart = json.loads(run.chart_spec_json)
    assert chart["data"], "chart must have at least one trace"
    assert run.table_json, "expected a summary table"
    steps = json.loads(run.steps_json)
    assert steps, "expected a non-empty audit trail"
    assert any(st["ok"] for st in steps), "at least one attempt must succeed"
    assert run.tokens and run.tokens > 0, "tokens must be captured from the provider"


@pytest.mark.usefixtures("_require_llm_key")
def test_analysis_runs_over_full_file_not_sample(_isolated_db):
    """Data-correctness: the per-status counts must sum to the FULL row_count
    (~99441), proving the code ran over the full file, not the 20-row sample."""
    dataset_id = _seed_dataset(_isolated_db, OLIST)
    prof = profile_csv(str(OLIST))
    full_row_count = prof.row_count
    assert len(prof.sample_rows) <= 20 < full_row_count

    run_id = run_agent(dataset_id, QUESTION)
    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)

    assert run.status == "completed", run.error_message
    table = json.loads(run.table_json)
    # Find the numeric count column and sum it.
    total = 0
    for row in table:
        nums = [v for v in row.values() if isinstance(v, (int, float))]
        if nums:
            total += max(nums)  # the count column (largest numeric per group row)
    assert total == full_row_count, (
        f"counts summed to {total}, expected full row_count {full_row_count} "
        "— code did not run over the full file"
    )


@pytest.mark.usefixtures("_require_llm_key")
def test_analysis_via_api_and_stream(api_client, _isolated_db):
    """HTTP round-trip: upload -> create run -> drain SSE stream -> fetch run."""
    with OLIST.open("rb") as fh:
        data = fh.read()
    up = api_client.post(
        "/datasets",
        files={"file": (OLIST.name, io.BytesIO(data), "text/csv")},
    )
    assert up.status_code == 200, up.text
    dataset_id = up.json()["data"]["dataset_id"]
    assert up.json()["data"]["row_count"] > 90000

    created = api_client.post(f"/datasets/{dataset_id}/runs", json={"question": QUESTION})
    assert created.status_code == 200
    run_id = created.json()["data"]["run_id"]

    # Drain the SSE stream until the terminal event.
    events = []
    with api_client.stream("GET", f"/runs/{run_id}/stream") as resp:
        assert resp.status_code == 200
        cur_event = None
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("event:"):
                cur_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and cur_event:
                events.append(cur_event)
                if cur_event in ("final", "error"):
                    break

    assert "plan" in events, f"expected a plan event, saw {events}"
    assert "final" in events, f"expected a final event, saw {events}"

    fetched = api_client.get(f"/runs/{run_id}")
    assert fetched.status_code == 200
    body = fetched.json()["data"]
    assert body["status"] == "completed", body.get("error")
    assert body["answer"]
    assert body["chart_spec"]
    assert body["table"]
    assert body["steps"]


def _table_cell_values(table: list[dict]) -> list:
    """Flatten every cell value across a list-of-records table."""
    vals: list = []
    for row in table:
        vals.extend(row.values())
    return vals


@pytest.mark.usefixtures("_require_llm_key")
def test_scalar_answer_carries_synthesized_table(_isolated_db):
    """Defect 1: a scalar/count question (no natural groupby) still returns a
    NON-EMPTY table — synthesized deterministically in finalize, not left null.

    Asserts the actual value: the count of delivered orders must match the full
    file (96478 in the olist sample)."""
    import pandas as pd

    dataset_id = _seed_dataset(_isolated_db, OLIST)
    full = pd.read_csv(str(OLIST))
    expected = int((full["order_status"] == "delivered").sum())

    run_id = run_agent(
        dataset_id,
        "How many orders have an order_status of 'delivered'? Return a single number.",
    )
    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)

    assert run.status == "completed", run.error_message
    assert run.table_json, "scalar answer must still carry a (synthesized) table"
    table = json.loads(run.table_json)
    assert table, "table must be non-empty"
    values = _table_cell_values(table)
    # The real delivered count must appear somewhere in the table cells.
    numeric = [int(v) for v in values if isinstance(v, (int, float))]
    assert expected in numeric, (
        f"expected delivered count {expected} in table cells, got {values}"
    )


@pytest.mark.usefixtures("_require_llm_key")
def test_scalar_answer_table_in_final_event_and_get_run(api_client, _isolated_db):
    """Defect 1 over HTTP: the `final` SSE event AND GET /runs/{id} both carry a
    non-empty table for a scalar count question."""
    with OLIST.open("rb") as fh:
        data = fh.read()
    up = api_client.post(
        "/datasets", files={"file": (OLIST.name, io.BytesIO(data), "text/csv")}
    )
    dataset_id = up.json()["data"]["dataset_id"]
    created = api_client.post(
        f"/datasets/{dataset_id}/runs",
        json={"question": "What is the total number of orders in this dataset? "
                          "Return a single count."},
    )
    run_id = created.json()["data"]["run_id"]

    final_payload = None
    with api_client.stream("GET", f"/runs/{run_id}/stream") as resp:
        cur_event = None
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("event:"):
                cur_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and cur_event:
                if cur_event in ("final", "error"):
                    final_payload = (cur_event, json.loads(line.split(":", 1)[1].strip()))
                    break

    assert final_payload is not None, "no terminal event"
    kind, payload = final_payload
    assert kind == "final", f"expected final, got {kind}: {payload}"
    assert payload["table"], "final event must carry a non-empty table for a scalar answer"

    body = api_client.get(f"/runs/{run_id}").json()["data"]
    assert body["status"] == "completed"
    assert body["table"], "GET /runs/{id} must carry a non-empty table for a scalar answer"


@pytest.mark.usefixtures("_require_llm_key")
def test_groupby_still_has_table_and_chart(_isolated_db):
    """Regression guard: the canonical groupby still yields BOTH a non-empty
    table and a chart_spec (Defect 1 fix must not strip the existing path)."""
    dataset_id = _seed_dataset(_isolated_db, OLIST)
    run_id = run_agent(dataset_id, QUESTION)
    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)

    assert run.status == "completed", run.error_message
    assert run.table_json and json.loads(run.table_json), "groupby table missing"
    assert run.chart_spec_json, "groupby chart_spec missing"
    assert json.loads(run.chart_spec_json)["data"], "chart must have a trace"


@pytest.mark.usefixtures("_require_llm_key")
def test_unanswerable_question_routes_to_failure_channel(api_client, _isolated_db):
    """Defect 2: a question about a column NOT in the olist_orders sample
    (`freight_value`/`customer_state` live in OTHER olist files) must NOT report
    a green success — it surfaces the unanswerable state via the `error` channel
    with the list of AVAILABLE columns, and is distinct from a sandbox-retry
    give-up failure."""
    with OLIST.open("rb") as fh:
        data = fh.read()
    up = api_client.post(
        "/datasets", files={"file": (OLIST.name, io.BytesIO(data), "text/csv")}
    )
    dataset_id = up.json()["data"]["dataset_id"]
    created = api_client.post(
        f"/datasets/{dataset_id}/runs",
        json={"question": "What is the average freight_value by customer_state?"},
    )
    run_id = created.json()["data"]["run_id"]

    terminal = None
    with api_client.stream("GET", f"/runs/{run_id}/stream") as resp:
        cur_event = None
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("event:"):
                cur_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and cur_event:
                if cur_event in ("final", "error"):
                    terminal = (cur_event, json.loads(line.split(":", 1)[1].strip()))
                    break

    assert terminal is not None, "no terminal event"
    kind, payload = terminal
    assert kind == "error", f"unanswerable must route to the error channel, got {kind}: {payload}"

    err = payload.get("error") or ""
    # Lists the columns that ARE available so the user can re-ask.
    assert "order_status" in err, f"available columns not listed in: {err!r}"
    assert "order_id" in err, f"available columns not listed in: {err!r}"
    # Distinct from a genuine sandbox-retry give-up failure.
    assert "gave up after" not in err, f"must not be a retry give-up: {err!r}"

    body = api_client.get(f"/runs/{run_id}").json()["data"]
    assert body["status"] == "failed", "unanswerable must persist a non-success status"
    assert body["answer"] in (None, ""), "must NOT carry a green success answer"
    assert "order_status" in (body["error"] or ""), "GET /runs must reflect available columns"
