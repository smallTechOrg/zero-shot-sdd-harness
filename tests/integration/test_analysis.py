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
