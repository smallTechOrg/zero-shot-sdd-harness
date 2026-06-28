"""DB model tests for the Local Data Analyst — no LLM key required.

Covers the db-migration slice: DatasetRow + QuestionRunRow models, tablenames,
key columns, the FK relationship, and roundtrip persistence with JSON-string
columns. Runs against the production SQLite driver via the _isolated_db fixture.
"""
import json

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from db.models import Base, DatasetRow, QuestionRunRow


# ---------------------------------------------------------------------------
# Structural assertions (models import, tablenames, columns, FK)
# ---------------------------------------------------------------------------

def test_models_import_and_base_exported():
    assert Base is not None
    assert DatasetRow.__tablename__ == "datasets"
    assert QuestionRunRow.__tablename__ == "question_runs"


def test_dataset_columns_present():
    cols = {c.name for c in DatasetRow.__table__.columns}
    expected = {
        "id", "name", "source_path", "duckdb_path", "table_name",
        "schema_json", "profile_json", "row_count", "status",
        "error_message", "created_at", "updated_at",
    }
    assert expected <= cols, f"missing: {expected - cols}"


def test_question_run_columns_present():
    cols = {c.name for c in QuestionRunRow.__table__.columns}
    expected = {
        "id", "dataset_id", "question", "plan", "sql", "trace_json",
        "result_json", "chart_json", "answer", "key_numbers_json",
        "cost_usd", "status", "error_message", "created_at", "updated_at",
    }
    assert expected <= cols, f"missing: {expected - cols}"


def test_question_run_has_fk_to_datasets():
    fks = list(QuestionRunRow.__table__.c.dataset_id.foreign_keys)
    assert len(fks) == 1
    target = fks[0].column
    assert target.table.name == "datasets"
    assert target.name == "id"


def test_old_runs_table_is_gone():
    # The transform_text "runs" table is superseded; nothing should define it.
    assert "runs" not in Base.metadata.tables
    assert {"datasets", "question_runs"} <= set(Base.metadata.tables)


def test_required_nullability():
    dcols = DatasetRow.__table__.columns
    assert dcols["name"].nullable is False
    assert dcols["schema_json"].nullable is False
    assert dcols["row_count"].nullable is False
    assert dcols["error_message"].nullable is True

    qcols = QuestionRunRow.__table__.columns
    assert qcols["dataset_id"].nullable is False
    assert qcols["question"].nullable is False
    # Optional analysis fields are nullable (populated as the run progresses).
    assert qcols["plan"].nullable is True
    assert qcols["sql"].nullable is True
    assert qcols["cost_usd"].nullable is True


# ---------------------------------------------------------------------------
# Persistence roundtrip (happy path)
# ---------------------------------------------------------------------------

def test_dataset_roundtrip_with_json_columns(_isolated_db):
    schema = {"region": "VARCHAR", "sales": "DOUBLE"}
    profile = {"row_count": 100, "columns": {"sales": {"min": 1, "max": 9}}}

    with Session(_isolated_db) as s:
        ds = DatasetRow(
            name="sales.csv",
            source_path="data/uploads/x/sales.csv",
            duckdb_path="data/duckdb/x.duckdb",
            table_name="sales",
            schema_json=json.dumps(schema),
            profile_json=json.dumps(profile),
            row_count=100,
        )
        s.add(ds)
        s.commit()
        ds_id = ds.id

    with Session(_isolated_db) as s:
        fetched = s.get(DatasetRow, ds_id)
        assert fetched is not None
        assert fetched.name == "sales.csv"
        assert fetched.row_count == 100
        assert fetched.status == "ready"  # default applied
        assert fetched.error_message is None
        assert fetched.created_at is not None
        # JSON survives the Text roundtrip.
        assert json.loads(fetched.schema_json) == schema
        assert json.loads(fetched.profile_json)["row_count"] == 100


def test_question_run_roundtrip_and_relationship(_isolated_db):
    with Session(_isolated_db) as s:
        ds = DatasetRow(
            name="sales.csv",
            source_path="p",
            duckdb_path="d",
            table_name="sales",
            schema_json="{}",
            profile_json="{}",
            row_count=10,
        )
        s.add(ds)
        s.commit()
        ds_id = ds.id

        run = QuestionRunRow(
            dataset_id=ds_id,
            question="Which region had the highest total sales?",
            plan="aggregate sales by region",
            sql="SELECT region, SUM(sales) FROM sales GROUP BY region",
            trace_json=json.dumps([{"step": "execute", "ok": True}]),
            result_json=json.dumps([{"region": "EMEA", "total": 42}]),
            chart_json=json.dumps({"type": "bar", "x": "region", "y": "total"}),
            answer="EMEA had the highest total sales.",
            key_numbers_json=json.dumps({"EMEA": 42}),
            cost_usd=0.0012,
        )
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        fetched = s.get(QuestionRunRow, run_id)
        assert fetched is not None
        assert fetched.dataset_id == ds_id
        assert fetched.status == "completed"  # default applied
        assert fetched.cost_usd == 0.0012
        assert json.loads(fetched.chart_json)["type"] == "bar"
        # Relationship navigations both directions.
        assert fetched.dataset.id == ds_id
        assert len(fetched.dataset.question_runs) == 1


# ---------------------------------------------------------------------------
# Edge case: minimal/optional fields left null
# ---------------------------------------------------------------------------

def test_question_run_minimal_optional_fields_null(_isolated_db):
    with Session(_isolated_db) as s:
        ds = DatasetRow(
            name="m.csv", source_path="p", duckdb_path="d", table_name="t",
            schema_json="{}", profile_json="{}", row_count=0,
        )
        s.add(ds)
        s.commit()
        ds_id = ds.id

        # Only required fields — mirrors a run created at ask-time before
        # the agent has produced plan/sql/answer.
        run = QuestionRunRow(dataset_id=ds_id, question="anything?")
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        run = s.get(QuestionRunRow, run_id)
        assert run.plan is None
        assert run.sql is None
        assert run.answer is None
        assert run.cost_usd is None
        assert run.status == "completed"


# ---------------------------------------------------------------------------
# Error path: required NOT NULL columns are enforced by the driver
# ---------------------------------------------------------------------------

def test_dataset_missing_required_field_raises(_isolated_db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    with Session(_isolated_db) as s:
        # row_count is NOT NULL with no default — omitting it must fail at flush.
        ds = DatasetRow(
            name="bad.csv", source_path="p", duckdb_path="d", table_name="t",
            schema_json="{}", profile_json="{}",
        )
        s.add(ds)
        with pytest.raises(IntegrityError):
            s.commit()


def test_inspector_sees_both_tables(_isolated_db):
    insp = inspect(_isolated_db)
    names = set(insp.get_table_names())
    assert {"datasets", "question_runs"} <= names
    assert "runs" not in names
