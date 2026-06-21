from typing import Any, TypedDict


class AgentState(TypedDict):
    # Identity
    run_id: int

    # Input (set at run start)
    user_input: str

    # Pipeline data (populated progressively by nodes)
    tool_call_history: list[dict[str, Any]]
    result: str | None

    # Control
    error: str | None          # set by any node on fatal failure
    iterations: int            # incremented by plan_action; guards against infinite loops
