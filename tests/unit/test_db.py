"""DB layer tests — no LLM key required."""
import json

from sqlalchemy.orm import Session

from db.models import DatasetRow, RunRow


def _make_dataset(**overrides) -> DatasetRow:
    defaults = dict(
        name="sales_2024",
        original_filename="sales_2024.csv",
        file_path="data/datasets/abc.csv",
        file_format="csv",
        size_bytes=1024,
        row_count=50000,
        column_count=7,
        profile_json=json.dumps({"columns": [], "quality_flags": [], "sample_rows": []}),
    )
    defaults.update(overrides)
    return DatasetRow(**defaults)


def test_dataset_row_roundtrip(_isolated_db):
    with Session(_isolated_db) as s:
        ds = _make_dataset()
        s.add(ds)
        s.commit()
        ds_id = ds.id

    with Session(_isolated_db) as s:
        fetched = s.get(DatasetRow, ds_id)
        assert fetched is not None
        assert fetched.name == "sales_2024"
        assert fetched.original_filename == "sales_2024.csv"
        assert fetched.file_format == "csv"
        assert fetched.size_bytes == 1024
        assert fetched.row_count == 50000
        assert fetched.column_count == 7
        assert json.loads(fetched.profile_json) == {
            "columns": [],
            "quality_flags": [],
            "sample_rows": [],
        }
        assert fetched.created_at is not None


def test_run_row_roundtrip_with_fk(_isolated_db):
    with Session(_isolated_db) as s:
        ds = _make_dataset()
        s.add(ds)
        s.commit()
        ds_id = ds.id

        run = RunRow(dataset_id=ds_id, question="What were total sales by region?")
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        fetched = s.get(RunRow, run_id)
        assert fetched is not None
        assert fetched.dataset_id == ds_id
        assert fetched.question == "What were total sales by region?"
        # defaults
        assert fetched.status == "pending"
        assert fetched.attempts == 0
        # nullable / Phase-2 fields default to None
        assert fetched.session_id is None
        assert fetched.generated_code is None
        assert fetched.result_json is None
        assert fetched.answer_text is None
        assert fetched.narrative is None
        assert fetched.key_numbers_json is None
        assert fetched.chart_json is None
        assert fetched.table_json is None
        assert fetched.tokens_used is None
        assert fetched.cost_estimate_usd is None
        assert fetched.error_message is None
        assert fetched.created_at is not None
        assert fetched.updated_at is not None


def test_run_row_null_session_and_defaults(_isolated_db):
    """A Phase-1 run has no session_id and starts pending with 0 attempts."""
    with Session(_isolated_db) as s:
        ds = _make_dataset()
        s.add(ds)
        s.commit()
        run = RunRow(dataset_id=ds.id, question="q", session_id=None)
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        assert run.session_id is None
        assert run.status == "pending"
        assert run.attempts == 0


def test_failed_run_persists_error(_isolated_db):
    """A failed run keeps analysis fields empty but records the error."""
    with Session(_isolated_db) as s:
        ds = _make_dataset()
        s.add(ds)
        s.commit()
        run = RunRow(dataset_id=ds.id, question="broken")
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        run.status = "failed"
        run.attempts = 3
        run.error_message = "code execution failed after retries"
        s.commit()

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        assert run.status == "failed"
        assert run.attempts == 3
        assert run.error_message == "code execution failed after retries"
        assert run.answer_text is None


def test_run_finalize_updates_fields(_isolated_db):
    with Session(_isolated_db) as s:
        ds = _make_dataset()
        s.add(ds)
        s.commit()
        run = RunRow(dataset_id=ds.id, question="What were total sales by region?")
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        run.status = "completed"
        run.attempts = 1
        run.answer_text = "Total sales were $4.2M."
        run.narrative = "North leads."
        run.key_numbers_json = json.dumps([{"label": "Total sales", "value": "$4.2M"}])
        run.chart_json = json.dumps({"mark": "bar"})
        run.table_json = json.dumps([{"region": "North", "amount": 1600000}])
        run.generated_code = "result = {'value': None}"
        run.result_json = json.dumps({"value": None, "table": [], "columns": []})
        s.commit()

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        assert run.status == "completed"
        assert run.attempts == 1
        assert run.answer_text == "Total sales were $4.2M."
        assert json.loads(run.key_numbers_json) == [
            {"label": "Total sales", "value": "$4.2M"}
        ]
        assert json.loads(run.table_json) == [{"region": "North", "amount": 1600000}]


def test_multiple_datasets_and_runs_unique_ids(_isolated_db):
    ds_ids = []
    run_ids = []
    with Session(_isolated_db) as s:
        for i in range(3):
            ds = _make_dataset(name=f"ds{i}")
            s.add(ds)
            s.flush()
            ds_ids.append(ds.id)
            run = RunRow(dataset_id=ds.id, question=f"q{i}")
            s.add(run)
            s.flush()
            run_ids.append(run.id)
        s.commit()

    assert len(set(ds_ids)) == 3
    assert len(set(run_ids)) == 3
