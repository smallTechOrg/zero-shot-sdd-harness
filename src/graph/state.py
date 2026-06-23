from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Skeleton transform slot (kept for /runs + existing tests)
    run_id: str
    input_text: str
    output_text: str

    # Analyst identity / context
    turn_id: str
    session_id: str
    table_name: str
    question: str
    schema: list[dict]
    sample: dict
    history: list[dict]

    # Analyst pipeline data
    sql_text: str | None
    result: dict | None

    # Output
    answer_text: str | None
    status: str

    # Control
    error: str | None
