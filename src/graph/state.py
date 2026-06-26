from typing import TypedDict, Any, Optional


class NodeTrace(TypedDict):
    node: str
    duration_ms: float


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    session_id: str

    # Input
    question: str
    dataframe: Any         # pd.DataFrame — NOT serialized to DB

    # Data derived from the DataFrame
    column_schema: list[dict]   # [{"name": str, "dtype": str}, ...]

    # Output
    answer: str

    # Phase 2 outputs (null in Phase 1)
    executed_code: str | None
    chart_data: dict | None   # {"type": "png", "data": "<base64>"}

    # Observability
    tokens_in: int
    tokens_out: int
    cost_usd: float
    model: str
    node_trace: list[NodeTrace]

    # Control
    error: str | None
    status: str
