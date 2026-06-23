from typing import TypedDict


class AnalystState(TypedDict, total=False):
    session_id: str
    dataset_table: str
    question: str
    schema_context: str
    sql: str
    sql_explanation: str
    rows: list[dict]
    row_count: int
    duration_ms: int
    answer: str
    table: list[dict]
    audit_id: str
    error: str | None
