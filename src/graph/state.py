from typing import TypedDict


class AgentState(TypedDict, total=False):
    run_id: str
    session_id: str
    dataset_id: str
    question: str
    schema: list[dict]      # [{name, type}]
    table_name: str
    sql: str
    columns: list[str]
    rows: list[list]
    row_count: int
    answer: str
    status: str
    error: str | None
