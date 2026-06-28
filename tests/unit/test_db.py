"""DB layer tests — no LLM key required."""
import json

from sqlalchemy.orm import Session

from db.models import DatasetRow, RunRow


def test_dataset_row_roundtrip(_isolated_db):
    with Session(_isolated_db) as s:
        ds = DatasetRow(
            filename="x.csv",
            path="/tmp/x.csv",
            row_count=10,
            schema_json=json.dumps([{"name": "a", "dtype": "int64"}]),
            sample_json=json.dumps([{"a": 1}]),
        )
        s.add(ds)
        s.commit()
        ds_id = ds.id

    with Session(_isolated_db) as s:
        fetched = s.get(DatasetRow, ds_id)
        assert fetched is not None
        assert fetched.filename == "x.csv"
        assert fetched.row_count == 10
        assert json.loads(fetched.schema_json)[0]["name"] == "a"


def test_run_row_roundtrip(_isolated_db):
    with Session(_isolated_db) as s:
        run = RunRow(dataset_id="ds1", question="hello?", status="running")
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        fetched = s.get(RunRow, run_id)
        assert fetched is not None
        assert fetched.dataset_id == "ds1"
        assert fetched.question == "hello?"
        assert fetched.status == "running"
        assert fetched.answer is None


def test_run_row_status_update(_isolated_db):
    with Session(_isolated_db) as s:
        run = RunRow(dataset_id="ds1", question="q", status="running")
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        run.status = "completed"
        run.answer = "the answer"
        s.commit()

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        assert run.status == "completed"
        assert run.answer == "the answer"


def test_multiple_runs_independent(_isolated_db):
    with Session(_isolated_db) as s:
        for i in range(3):
            s.add(RunRow(dataset_id="ds1", question=f"q{i}", status="running"))
        s.commit()
        runs = s.query(RunRow).all()
        ids = [r.id for r in runs]

    assert len(ids) == 3
    assert len(set(ids)) == 3
