"""Schema tests for the data-analysis models: table creation, FK cascade, JSON round-trip.

Runs against an isolated SQLite file with FK enforcement enabled (SQLite needs
PRAGMA foreign_keys=ON per connection for ON DELETE CASCADE to fire).
"""

import json

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base, DatasetRow, RunRow, RunStepRow


@event.listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/schema.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as s:
        yield s
    engine.dispose()


def test_all_tables_created(session):
    inspector = inspect(session.get_bind())
    tables = set(inspector.get_table_names())
    assert {"datasets", "runs", "run_steps"} <= tables


def _make_graph(session) -> tuple[str, str, str]:
    """Insert a Dataset + Run + RunStep; return their ids."""
    dataset = DatasetRow(
        name="sales.csv",
        file_path="data/datasets/sales.csv",
        row_count=100,
        col_count=5,
        profile_json=json.dumps({"columns": [{"name": "amount", "dtype": "float"}]}),
        size_bytes=2048,
    )
    session.add(dataset)
    session.flush()

    run = RunRow(
        dataset_id=dataset.id,
        question="What is the total amount?",
        status="completed",
        plan="sum the amount column",
        final_code="df['amount'].sum()",
        prose="The total is 1234.",
        chart_json=json.dumps({"type": "bar", "data": [1, 2, 3]}),
        table_json=json.dumps({"columns": ["total"], "rows": [[1234]]}),
        prompt_tokens=120,
        completion_tokens=40,
        cost_usd=0.0021,
        step_count=2,
    )
    session.add(run)
    session.flush()

    step = RunStepRow(
        run_id=run.id,
        step_index=0,
        node="execute",
        status="worked",
        code="df['amount'].sum()",
        result_summary="scalar: 1234",
        detail="executed the aggregate",
        latency_ms=85,
    )
    session.add(step)
    session.commit()
    return dataset.id, run.id, step.id


def test_fk_relationship_navigates(session):
    dataset_id, run_id, step_id = _make_graph(session)
    session.expire_all()

    dataset = session.get(DatasetRow, dataset_id)
    assert len(dataset.runs) == 1
    run = dataset.runs[0]
    assert run.id == run_id
    assert run.dataset.id == dataset_id
    assert len(run.steps) == 1
    assert run.steps[0].id == step_id
    assert run.steps[0].run.id == run_id


def test_cascade_delete_removes_runs_and_steps(session):
    dataset_id, run_id, step_id = _make_graph(session)

    dataset = session.get(DatasetRow, dataset_id)
    session.delete(dataset)
    session.commit()
    session.expire_all()

    assert session.get(DatasetRow, dataset_id) is None
    assert session.get(RunRow, run_id) is None, "deleting a dataset must cascade to its runs"
    assert session.get(RunStepRow, step_id) is None, "deleting a dataset must cascade to run steps"


def test_json_columns_round_trip(session):
    profile = {"columns": [{"name": "amount", "dtype": "float", "min": 0, "max": 999}]}
    chart = {"type": "line", "series": [{"x": 1, "y": 2}]}
    table = {"columns": ["k", "v"], "rows": [["a", 1], ["b", 2]]}

    dataset = DatasetRow(
        name="d.csv",
        file_path="data/datasets/d.csv",
        row_count=10,
        col_count=2,
        profile_json=json.dumps(profile),
        size_bytes=512,
    )
    session.add(dataset)
    session.flush()
    run = RunRow(
        dataset_id=dataset.id,
        question="q",
        status="completed",
        chart_json=json.dumps(chart),
        table_json=json.dumps(table),
    )
    session.add(run)
    session.commit()

    dataset_id, run_id = dataset.id, run.id
    session.expire_all()

    loaded_ds = session.get(DatasetRow, dataset_id)
    loaded_run = session.get(RunRow, run_id)
    assert json.loads(loaded_ds.profile_json) == profile
    assert json.loads(loaded_run.chart_json) == chart
    assert json.loads(loaded_run.table_json) == table
