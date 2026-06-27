"""Offline API suite for the Phase-2 routes.

Stub provider + in-memory SQLite, zero network. Exercises the full upload ->
datasets -> ask -> runs journey through the `api_client` TestClient. The stub
LLM returns node-tagged canned output, so `/ask` returns a `[stub]` answer with
recorded steps — enough to prove the route plumbing end to end without a key.
"""
import io

import pytest


@pytest.fixture(autouse=True)
def _force_stub_provider(monkeypatch):
    """Pin the offline stub provider regardless of any key present in `.env`.

    This suite is the offline guarantee — no network even when a real key is
    configured locally. Set ahead of the settings-singleton reset so both the
    graph and `/health` resolve to `stub`.
    """
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "stub")
    import config.settings as m
    m._settings = None


_CSV = "value,label\n10,a\n20,b\n30,c\n"


def _upload_csv(client, *, name="sample.csv", body=_CSV):
    files = {"file": (name, io.BytesIO(body.encode()), "text/csv")}
    return client.post("/upload", files=files)


# --- upload --------------------------------------------------------------


def test_upload_csv_returns_counts(api_client):
    r = _upload_csv(api_client)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["filename"] == "sample.csv"
    assert data["format"] == "csv"
    assert data["row_count"] == 3
    assert data["col_count"] == 2
    assert data["columns"] == ["value", "label"]
    # Phase 4 (C30): upload marks notes pending and fires the async notes job.
    assert data["auto_notes_status"] == "pending"


def test_upload_rejects_bad_extension(api_client):
    files = {"file": ("notes.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}
    r = api_client.post("/upload", files=files)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] in ("bad_extension", "unparseable_file")


def test_upload_rejects_empty_file(api_client):
    files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    r = api_client.post("/upload", files=files)
    assert r.status_code == 400


def test_duplicate_upload_returns_409(api_client):
    first = _upload_csv(api_client)
    assert first.status_code == 200
    dup = _upload_csv(api_client)
    assert dup.status_code == 409
    detail = dup.json()["detail"]
    assert detail["code"] == "duplicate_dataset"
    assert detail["match_type"] in ("content_and_name", "content", "name")
    assert detail["existing_dataset_id"] == first.json()["data"]["dataset_id"]


def test_duplicate_upload_force_overrides(api_client):
    first = _upload_csv(api_client)
    assert first.status_code == 200
    forced = api_client.post(
        "/upload?force=true",
        files={"file": ("sample.csv", io.BytesIO(_CSV.encode()), "text/csv")},
    )
    assert forced.status_code == 200
    assert forced.json()["data"]["dataset_id"] != first.json()["data"]["dataset_id"]


# --- datasets ------------------------------------------------------------


def test_datasets_list_includes_uploaded(api_client):
    up = _upload_csv(api_client)
    dataset_id = up.json()["data"]["dataset_id"]
    r = api_client.get("/datasets")
    assert r.status_code == 200
    rows = r.json()["data"]
    assert any(d["id"] == dataset_id for d in rows)
    row = next(d for d in rows if d["id"] == dataset_id)
    assert row["origin"] == "uploaded"
    assert row["stale"] is False
    assert row["derivation_description"] is None


def test_dataset_detail_has_columns_schema(api_client):
    up = _upload_csv(api_client)
    dataset_id = up.json()["data"]["dataset_id"]
    r = api_client.get(f"/datasets/{dataset_id}")
    assert r.status_code == 200
    data = r.json()["data"]
    schema = {c["name"]: c["dtype"] for c in data["columns_schema"]}
    assert schema["value"] == "integer"
    assert schema["label"] == "text"


def test_dataset_detail_404_when_missing(api_client):
    r = api_client.get("/datasets/does-not-exist")
    assert r.status_code == 404


def test_dataset_preview_returns_rows(api_client):
    up = _upload_csv(api_client)
    dataset_id = up.json()["data"]["dataset_id"]
    r = api_client.get(f"/datasets/{dataset_id}/preview?rows=2")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["columns"] == ["value", "label"]
    assert len(data["rows"]) == 2
    assert data["rows"][0]["value"] == 10


def test_dataset_preview_formats_nan_as_null(api_client):
    body = "value,label\n10,a\n,b\n"
    up = _upload_csv(api_client, name="withnan.csv", body=body)
    dataset_id = up.json()["data"]["dataset_id"]
    r = api_client.get(f"/datasets/{dataset_id}/preview")
    assert r.status_code == 200
    rows = r.json()["data"]["rows"]
    # second row's `value` is NaN -> null
    assert rows[1]["value"] is None


def test_delete_dataset_removes_it(api_client):
    up = _upload_csv(api_client)
    dataset_id = up.json()["data"]["dataset_id"]
    r = api_client.delete(f"/datasets/{dataset_id}")
    assert r.status_code == 200
    assert api_client.get(f"/datasets/{dataset_id}").status_code == 404


def test_delete_dataset_404_when_missing(api_client):
    r = api_client.delete("/datasets/does-not-exist")
    assert r.status_code == 404


def test_delete_all_datasets(api_client):
    _upload_csv(api_client)
    _upload_csv(api_client, name="other.csv", body="x,y\n1,2\n")
    r = api_client.delete("/datasets")
    assert r.status_code == 200
    assert api_client.get("/datasets").json()["data"] == []


# --- ask + runs ----------------------------------------------------------


def test_ask_single_dataset_returns_answer(api_client):
    up = _upload_csv(api_client)
    dataset_id = up.json()["data"]["dataset_id"]
    r = api_client.post("/ask", json={"dataset_id": dataset_id, "question": "describe it"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["type"] == "answer"
    assert data["run_id"]
    assert data["dataset_ids"] == [dataset_id]
    assert data["answer_markdown"]  # stub answer is non-empty
    assert data["answer_html"]  # rendered from markdown
    assert isinstance(data["steps"], list)
    assert len(data["steps"]) >= 1
    assert data["status"] == "completed"
    assert data["suggested_questions"] == []
    # C29 prompt_breakdown is built from token estimates for every run regardless
    # of provider (spec/api.md), so it is a populated dict — not {} — in Phase 3.
    assert isinstance(data["prompt_breakdown"], dict)
    assert data["prompt_breakdown"]  # non-empty: carries the measured components
    assert "total_prompt" in data["prompt_breakdown"]
    # All named spec components must be present (spec/capabilities/context-window-display.md).
    assert "dataset_notes" in data["prompt_breakdown"]


def test_ask_404_when_dataset_missing(api_client):
    r = api_client.post("/ask", json={"dataset_id": "ghost", "question": "hi"})
    assert r.status_code == 404


def test_runs_current_reflects_last_run(api_client):
    up = _upload_csv(api_client)
    dataset_id = up.json()["data"]["dataset_id"]
    ask = api_client.post("/ask", json={"dataset_id": dataset_id, "question": "describe it"})
    run_id = ask.json()["data"]["run_id"]
    r = api_client.get("/runs/current")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["run_id"] == run_id
    assert data["status"] == "completed"


def test_get_run_by_id_returns_query_run(api_client):
    up = _upload_csv(api_client)
    dataset_id = up.json()["data"]["dataset_id"]
    ask = api_client.post("/ask", json={"dataset_id": dataset_id, "question": "describe it"})
    run_id = ask.json()["data"]["run_id"]
    r = api_client.get(f"/runs/{run_id}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["run_id"] == run_id
    assert data["status"] == "completed"
    assert "iteration_count" in data


# --- stats ---------------------------------------------------------------


def test_stats_daily_always_200(api_client):
    r = api_client.get("/stats/daily")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "date" in data
    assert "model" in data
    assert data["context_limit"] >= 1
    assert data["query_count"] == 0


def test_stats_daily_counts_completed_runs(api_client):
    up = _upload_csv(api_client)
    dataset_id = up.json()["data"]["dataset_id"]
    api_client.post("/ask", json={"dataset_id": dataset_id, "question": "describe it"})
    r = api_client.get("/stats/daily")
    data = r.json()["data"]
    assert data["query_count"] == 1


# --- C16: notes_file tests -----------------------------------------------


def test_upload_notes_file_stored_as_context(api_client):
    """C16: notes_file content is stored as the dataset's context field."""
    files = {
        "file": ("data.csv", io.BytesIO(_CSV.encode()), "text/csv"),
        "notes_file": ("notes.txt", io.BytesIO(b"These are my notes."), "text/plain"),
    }
    r = api_client.post("/upload", files=files)
    assert r.status_code == 200, r.text
    dataset_id = r.json()["data"]["dataset_id"]

    detail = api_client.get(f"/datasets/{dataset_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["context"] == "These are my notes."


def test_upload_notes_file_overrides_form_context(api_client):
    """C16: notes_file wins when both form context and notes_file are supplied."""
    files = {
        "file": ("data.csv", io.BytesIO(_CSV.encode()), "text/csv"),
        "notes_file": ("notes.txt", io.BytesIO(b"notes win"), "text/plain"),
    }
    data = {"context": "form context"}
    r = api_client.post("/upload", files=files, data=data)
    assert r.status_code == 200, r.text
    dataset_id = r.json()["data"]["dataset_id"]

    detail = api_client.get(f"/datasets/{dataset_id}")
    assert detail.json()["data"]["context"] == "notes win"


def test_upload_notes_file_truncated_at_4000(api_client):
    """C16: notes content over 4000 chars is truncated to exactly 4000."""
    long_notes = "x" * 5000
    files = {
        "file": ("data.csv", io.BytesIO(_CSV.encode()), "text/csv"),
        "notes_file": ("notes.txt", io.BytesIO(long_notes.encode()), "text/plain"),
    }
    r = api_client.post("/upload", files=files)
    assert r.status_code == 200, r.text
    dataset_id = r.json()["data"]["dataset_id"]

    detail = api_client.get(f"/datasets/{dataset_id}")
    assert len(detail.json()["data"]["context"]) == 4000


# --- C1/C11: Multi-format upload tests -----------------------------------


def test_upload_tsv_parses_correctly(api_client):
    """C1/C11: TSV files are parsed correctly."""
    tsv_body = "col_a\tcol_b\n1\talpha\n2\tbeta\n"
    files = {"file": ("data.tsv", io.BytesIO(tsv_body.encode()), "text/tab-separated-values")}
    r = api_client.post("/upload", files=files)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["row_count"] == 2
    assert data["col_count"] == 2


def test_upload_txt_parses_correctly(api_client):
    """C1/C11: .txt files treated as TSV."""
    tsv_body = "col_a\tcol_b\n1\talpha\n2\tbeta\n"
    files = {"file": ("data.txt", io.BytesIO(tsv_body.encode()), "text/plain")}
    r = api_client.post("/upload", files=files)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["row_count"] == 2
    assert data["col_count"] == 2


def test_upload_json_parses_correctly(api_client):
    """C1/C11: JSON files are parsed correctly."""
    import json as _json
    json_body = _json.dumps([{"col_a": 1, "col_b": "alpha"}, {"col_a": 2, "col_b": "beta"}])
    files = {"file": ("data.json", io.BytesIO(json_body.encode()), "application/json")}
    r = api_client.post("/upload", files=files)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["row_count"] == 2
    assert data["col_count"] == 2


def test_upload_xlsx_parses_correctly(api_client):
    """C1/C11: XLSX files are parsed correctly."""
    import pandas as pd

    buf = io.BytesIO()
    pd.DataFrame({"col_a": [1, 2], "col_b": ["alpha", "beta"]}).to_excel(buf, index=False)
    buf.seek(0)
    files = {
        "file": (
            "data.xlsx",
            buf,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    r = api_client.post("/upload", files=files)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["row_count"] == 2
    assert data["col_count"] == 2


# --- C27: Parquet-preference / fallback tests ----------------------------


def test_upload_creates_parquet_alongside_csv(api_client):
    """C27: upload writes both .csv and .parquet for each dataset."""
    from pathlib import Path
    import api.upload as upload_module

    r = _upload_csv(api_client)
    assert r.status_code == 200, r.text
    dataset_id = r.json()["data"]["dataset_id"]

    parquet_path = upload_module.UPLOADS_DIR / f"{dataset_id}.parquet"
    assert parquet_path.exists(), f"Parquet file not found: {parquet_path}"


def test_peek_columns_prefers_parquet(tmp_path):
    """C27: _peek_columns returns columns from Parquet when both Parquet and CSV exist."""
    import pandas as pd
    from graph import runner

    dataset_id = "test-peek-parquet"
    csv_path = tmp_path / f"{dataset_id}.csv"
    parquet_path = tmp_path / f"{dataset_id}.parquet"

    # Write CSV with different columns than Parquet to confirm Parquet wins.
    pd.DataFrame({"csv_col": [1, 2]}).to_csv(csv_path, index=False)
    pd.DataFrame({"parquet_col": [1, 2]}).to_parquet(parquet_path, index=False)

    original_uploads_dir = runner._uploads_dir

    def _mock_uploads_dir():
        return tmp_path

    runner._uploads_dir = _mock_uploads_dir
    try:
        cols = runner._peek_columns(dataset_id)
    finally:
        runner._uploads_dir = original_uploads_dir

    assert cols == ["parquet_col"]


def test_peek_columns_falls_back_to_csv(tmp_path):
    """C27: _peek_columns falls back to CSV when Parquet is absent."""
    import pandas as pd
    from graph import runner

    dataset_id = "test-peek-csv"
    csv_path = tmp_path / f"{dataset_id}.csv"
    pd.DataFrame({"csv_only_col": [1, 2]}).to_csv(csv_path, index=False)
    # No Parquet file written.

    original_uploads_dir = runner._uploads_dir

    def _mock_uploads_dir():
        return tmp_path

    runner._uploads_dir = _mock_uploads_dir
    try:
        cols = runner._peek_columns(dataset_id)
    finally:
        runner._uploads_dir = original_uploads_dir

    assert cols == ["csv_only_col"]


# --- D1: DELETE /datasets/{id} returns 409 when a run is running --------


def test_delete_dataset_with_running_run_returns_409(api_client, _isolated_db):
    """Fix A (D1): DELETE must return 409 `dataset_in_use` when a run is running."""
    from sqlalchemy.orm import sessionmaker
    from db.models import QueryRunRow

    # Upload a dataset and run /ask on it (stub; completes OK).
    up = _upload_csv(api_client)
    assert up.status_code == 200, up.text
    dataset_id = up.json()["data"]["dataset_id"]

    ask = api_client.post("/ask", json={"dataset_id": dataset_id, "question": "describe it"})
    assert ask.status_code == 200, ask.text
    run_id = ask.json()["data"]["run_id"]

    # Patch the completed run to status="running" using the isolated DB engine.
    Session = sessionmaker(bind=_isolated_db, autoflush=False, autocommit=False)
    with Session() as db_session:
        run_row = db_session.get(QueryRunRow, run_id)
        assert run_row is not None, "Run row missing after /ask"
        run_row.status = "running"
        db_session.commit()

    # DELETE should now fail with 409.
    r = api_client.delete(f"/datasets/{dataset_id}")
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "dataset_in_use"


# --- D2: _delete_one cascades runs listed in dataset_ids_json -----------


def test_delete_dataset_cascades_runs_via_dataset_ids_json(api_client, _isolated_db):
    """Fix B (D2): deleting a secondary dataset also removes runs in dataset_ids_json."""
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker
    from db.models import QueryRunRow

    # Upload two datasets.
    up_a = _upload_csv(api_client, name="a.csv")
    assert up_a.status_code == 200, up_a.text
    a_id = up_a.json()["data"]["dataset_id"]

    up_b = _upload_csv(api_client, name="b.csv", body="x,y\n1,2\n3,4\n")
    assert up_b.status_code == 200, up_b.text
    b_id = up_b.json()["data"]["dataset_id"]

    # Run /ask with both dataset ids — this run references B as a secondary.
    ask = api_client.post(
        "/ask", json={"dataset_ids": [a_id, b_id], "question": "compare them"}
    )
    assert ask.status_code == 200, ask.text
    run_id = ask.json()["data"]["run_id"]

    # Confirm the run was written and completed.
    Session = sessionmaker(bind=_isolated_db, autoflush=False, autocommit=False)
    with Session() as db_session:
        run_row = db_session.get(QueryRunRow, run_id)
        assert run_row is not None, "Run row missing after /ask"

    # Delete dataset B (the secondary participant).
    r = api_client.delete(f"/datasets/{b_id}")
    assert r.status_code == 200, r.text

    # The run referencing B must now be gone from the DB.
    with Session() as db_session:
        orphaned = db_session.get(QueryRunRow, run_id)
        assert orphaned is None, (
            f"Run {run_id} still present after deleting dataset B "
            "(dataset_ids_json cascade missed it)"
        )


# --- D4: Settings API tests -----------------------------------------------


def test_get_settings_returns_defaults(api_client):
    r = api_client.get("/settings")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "llm_model" in data
    assert "max_iterations" in data
    assert "price_input_per_million" in data
    assert "price_output_per_million" in data


def test_patch_and_read_settings(api_client):
    r = api_client.patch("/settings", json={"max_iterations": "10"})
    assert r.status_code == 200
    assert r.json()["data"]["max_iterations"] == "10"
    # Clear it
    r2 = api_client.patch("/settings", json={"max_iterations": None})
    assert r2.status_code == 200


# --- D8: charts_json persisted on run ------------------------------------


def test_charts_json_persisted_on_run(api_client):
    # Smoke: a completed run row should have charts_json accessible (empty for stub)
    r = api_client.post("/upload", files={"file": ("t.csv", b"a,b\n1,2\n3,4", "text/csv")})
    ds_id = r.json()["data"]["dataset_id"]
    r2 = api_client.post("/ask", json={"dataset_id": ds_id, "question": "describe"})
    assert r2.status_code == 200
    # charts in response may be [] for stub but key must exist
    assert "charts" in r2.json()["data"]
