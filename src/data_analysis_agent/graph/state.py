from typing import TypedDict


class AgentState(TypedDict, total=False):
    run_id: str
    query_record_id: str
    dataset_id: str
    question: str
    csv_path: str
    column_names: list[str]
    row_count: int
    query_history: list[dict]
    iteration_count: int
    llm_response: str
    answer: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None
    api_request_count: int
    error: str | None
