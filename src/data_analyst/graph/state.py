from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    # Identity / inputs
    session_id: int
    question: str
    audit_entry_id: int | None

    # Token-economy context (schema + <= N sample rows only)
    dataset_contexts: list[dict[str, Any]]
    relevant_tables: list[str]
    complexity: str

    # Pipeline data
    generated_sql: str | None
    result_columns: list[str] | None
    result_rows: list[list[Any]] | None
    row_count: int | None
    duration_ms: int | None
    answer_text: str | None
    retried: bool

    # Control
    error: str | None
    status: str
