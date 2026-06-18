from typing import TypedDict, Any


class AgentState(TypedDict, total=False):
    run_id: str
    session_id: str
    question: str
    df_columns: list[str]
    action_history: list[dict[str, Any]]
    iteration_count: int
    llm_response: str
    final_answer: str | None
    tokens_input: int
    tokens_output: int
    error: str | None
