"""Data-layer model tests for the 4 data-analyst tables — no LLM key required."""
from sqlalchemy.orm import Session

from db.models import (
    ConversationSessionRow,
    DatasetRow,
    QueryRunRow,
    SettingRow,
)
import db.session as session_module  # noqa: F401  (parity with test_db.py import style)


def test_dataset_row_roundtrip(_isolated_db):
    cols = [{"name": "a", "dtype": "int64"}, {"name": "b", "dtype": "object"}]
    with Session(_isolated_db) as s:
        ds = DatasetRow(
            filename="sales.csv",
            file_path="uploads/x.csv",
            row_count=100,
            col_count=2,
            columns_json=cols,
            content_hash="deadbeef",
            format="csv",
            origin="uploaded",
        )
        s.add(ds)
        s.commit()
        ds_id = ds.id

    with Session(_isolated_db) as s:
        fetched = s.get(DatasetRow, ds_id)
        assert fetched is not None
        assert fetched.id == ds_id  # uuid PK auto-assigned
        assert fetched.filename == "sales.csv"
        assert fetched.row_count == 100
        assert fetched.col_count == 2
        # JSON column round-trips equal
        assert fetched.columns_json == cols
        assert fetched.content_hash == "deadbeef"
        assert fetched.format == "csv"
        assert fetched.origin == "uploaded"
        # nullable fields default to None
        assert fetched.context is None
        assert fetched.derived_from_run_id is None
        assert fetched.derived_from_dataset_ids is None
        assert fetched.context_facts is None
        # timestamps populated
        assert fetched.created_at is not None
        assert fetched.updated_at is not None


def test_dataset_row_derived_lineage_json(_isolated_db):
    parents = ["ds-1", "ds-2"]
    facts = [{"fact": "high nulls in col x"}]
    with Session(_isolated_db) as s:
        ds = DatasetRow(
            filename="derived.csv",
            file_path="uploads/d.csv",
            row_count=10,
            col_count=1,
            columns_json=[{"name": "a", "dtype": "int64"}],
            content_hash="cafe",
            format="csv",
            origin="derived",
            derived_from_run_id="run-7",
            derived_from_dataset_ids=parents,
            derivation_code="df.dropna()",
            context_facts=facts,
        )
        s.add(ds)
        s.commit()
        ds_id = ds.id

    with Session(_isolated_db) as s:
        fetched = s.get(DatasetRow, ds_id)
        assert fetched.origin == "derived"
        assert fetched.derived_from_run_id == "run-7"
        assert fetched.derived_from_dataset_ids == parents
        assert fetched.derivation_code == "df.dropna()"
        assert fetched.context_facts == facts


def test_query_run_row_defaults(_isolated_db):
    with Session(_isolated_db) as s:
        qr = QueryRunRow(question="What is the average of col a?")
        s.add(qr)
        s.commit()
        qr_id = qr.id

    with Session(_isolated_db) as s:
        fetched = s.get(QueryRunRow, qr_id)
        assert fetched is not None
        assert fetched.id == qr_id  # uuid PK auto-assigned
        assert fetched.question == "What is the average of col a?"
        # defaults
        assert fetched.status == "pending"
        assert fetched.iteration_count == 0
        assert fetched.tokens_input == 0
        assert fetched.tokens_output == 0
        # nullable fields
        assert fetched.dataset_id is None
        assert fetched.session_id is None
        assert fetched.answer is None
        assert fetched.action_history is None
        assert fetched.created_at is not None


def test_query_run_row_action_history_json(_isolated_db):
    history = [{"action": "df.mean()", "result": "5.0", "is_error": False}]
    with Session(_isolated_db) as s:
        qr = QueryRunRow(
            question="avg?",
            answer="The average is 5.",
            status="completed",
            action_history=history,
            iteration_count=3,
            tokens_input=120,
            tokens_output=45,
            dataset_ids_json=["ds-1"],
        )
        s.add(qr)
        s.commit()
        qr_id = qr.id

    with Session(_isolated_db) as s:
        fetched = s.get(QueryRunRow, qr_id)
        assert fetched.status == "completed"
        assert fetched.answer == "The average is 5."
        assert fetched.action_history == history
        assert fetched.iteration_count == 3
        assert fetched.tokens_input == 120
        assert fetched.tokens_output == 45
        assert fetched.dataset_ids_json == ["ds-1"]


def test_conversation_session_row_roundtrip(_isolated_db):
    ids = ["ds-1", "ds-2"]
    with Session(_isolated_db) as s:
        sess = ConversationSessionRow(
            name="Q3 analysis",
            dataset_id="ds-1",
            dataset_ids_json=ids,
        )
        s.add(sess)
        s.commit()
        sess_id = sess.id

    with Session(_isolated_db) as s:
        fetched = s.get(ConversationSessionRow, sess_id)
        assert fetched is not None
        assert fetched.id == sess_id  # uuid PK auto-assigned
        assert fetched.name == "Q3 analysis"
        assert fetched.dataset_id == "ds-1"
        assert fetched.dataset_ids_json == ids
        assert fetched.created_at is not None
        assert fetched.updated_at is not None


def test_conversation_session_row_nullable_fields(_isolated_db):
    with Session(_isolated_db) as s:
        sess = ConversationSessionRow()
        s.add(sess)
        s.commit()
        sess_id = sess.id

    with Session(_isolated_db) as s:
        fetched = s.get(ConversationSessionRow, sess_id)
        assert fetched.name is None
        assert fetched.dataset_id is None
        assert fetched.dataset_ids_json is None


def test_setting_row_uses_key_as_pk(_isolated_db):
    with Session(_isolated_db) as s:
        setting = SettingRow(key="global_memory", value="remember the user prefers SI units")
        s.add(setting)
        s.commit()

    # fetch by the caller-supplied key (NOT a uuid)
    with Session(_isolated_db) as s:
        fetched = s.get(SettingRow, "global_memory")
        assert fetched is not None
        assert fetched.key == "global_memory"
        assert fetched.value == "remember the user prefers SI units"
        assert fetched.updated_at is not None


def test_setting_row_value_nullable(_isolated_db):
    with Session(_isolated_db) as s:
        setting = SettingRow(key="max_iterations")
        s.add(setting)
        s.commit()

    with Session(_isolated_db) as s:
        fetched = s.get(SettingRow, "max_iterations")
        assert fetched is not None
        assert fetched.key == "max_iterations"
        assert fetched.value is None
