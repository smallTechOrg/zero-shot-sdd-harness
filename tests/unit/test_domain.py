"""Pydantic domain-entity tests — no LLM key required.

Verifies each domain model maps from its ORM row (from_attributes) and from a
plain dict.
"""
from datetime import datetime, timezone

from db.models import (
    ConversationSessionRow,
    DatasetRow,
    QueryRunRow,
    SettingRow,
)
from domain import ConversationSession, Dataset, QueryRun, Setting

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_dataset_from_orm_row():
    cols = [{"name": "a", "dtype": "int64"}]
    row = DatasetRow(
        id="ds-1",
        filename="sales.csv",
        file_path="uploads/ds-1.csv",
        row_count=42,
        col_count=1,
        columns_json=cols,
        content_hash="abc",
        format="csv",
        origin="uploaded",
        created_at=_NOW,
        updated_at=_NOW,
    )
    dto = Dataset.model_validate(row)
    assert dto.id == "ds-1"
    assert dto.filename == "sales.csv"
    assert dto.row_count == 42
    assert dto.col_count == 1
    assert dto.columns_json == cols
    assert dto.origin == "uploaded"
    assert dto.context is None
    assert dto.created_at == _NOW


def test_dataset_from_dict():
    dto = Dataset(
        id="ds-2",
        filename="x.csv",
        file_path="uploads/ds-2.csv",
        row_count=1,
        col_count=1,
        columns_json=[{"name": "a", "dtype": "object"}],
        content_hash="hash",
        format="csv",
        origin="derived",
        derived_from_dataset_ids=["ds-1"],
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert dto.origin == "derived"
    assert dto.derived_from_dataset_ids == ["ds-1"]


def test_query_run_from_orm_row():
    history = [{"action": "df.mean()", "result": "5.0", "is_error": False}]
    row = QueryRunRow(
        id="run-1",
        question="avg?",
        answer="5",
        status="completed",
        action_history=history,
        iteration_count=2,
        tokens_input=10,
        tokens_output=5,
        dataset_ids_json=["ds-1"],
        created_at=_NOW,
        updated_at=_NOW,
    )
    dto = QueryRun.model_validate(row)
    assert dto.id == "run-1"
    assert dto.question == "avg?"
    assert dto.answer == "5"
    assert dto.status == "completed"
    assert dto.action_history == history
    assert dto.iteration_count == 2
    assert dto.tokens_input == 10
    assert dto.tokens_output == 5
    assert dto.dataset_ids_json == ["ds-1"]


def test_query_run_from_dict_defaults():
    dto = QueryRun(
        id="run-2",
        question="q?",
        status="pending",
        iteration_count=0,
        tokens_input=0,
        tokens_output=0,
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert dto.status == "pending"
    assert dto.answer is None
    assert dto.session_id is None


def test_conversation_session_from_orm_row():
    row = ConversationSessionRow(
        id="sess-1",
        name="My analysis",
        dataset_id="ds-1",
        dataset_ids_json=["ds-1", "ds-2"],
        created_at=_NOW,
        updated_at=_NOW,
    )
    dto = ConversationSession.model_validate(row)
    assert dto.id == "sess-1"
    assert dto.name == "My analysis"
    assert dto.dataset_id == "ds-1"
    assert dto.dataset_ids_json == ["ds-1", "ds-2"]


def test_conversation_session_from_dict():
    dto = ConversationSession(
        id="sess-2",
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert dto.id == "sess-2"
    assert dto.name is None
    assert dto.dataset_ids_json is None


def test_setting_from_orm_row():
    row = SettingRow(
        key="global_memory",
        value="prefers SI units",
        updated_at=_NOW,
    )
    dto = Setting.model_validate(row)
    assert dto.key == "global_memory"
    assert dto.value == "prefers SI units"
    assert dto.updated_at == _NOW


def test_setting_from_dict_value_optional():
    dto = Setting(key="max_iterations", updated_at=_NOW)
    assert dto.key == "max_iterations"
    assert dto.value is None
