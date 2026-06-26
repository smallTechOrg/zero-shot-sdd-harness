from typing import TypedDict


class AgentState(TypedDict, total=False):
    """ReAct loop state (LangGraph). `total=False` per skeleton convention —
    nodes populate fields progressively. Never a dataclass/Pydantic model.
    """

    # Identity
    run_id: str                          # query_runs.id, set at initialisation

    # Input
    dataset_ids: list[str]               # datasets to load (explicit or C19 selector)
    dataset_context: str | None          # concatenated dataset notes + schema for the prompt
    session_id: str | None               # set when the run belongs to a conversation session
    question: str                        # the user's plain-English question
    conversation_history: list[dict]     # prior turns {question, answer} for the session

    # Pipeline data (populated progressively by nodes)
    action_history: list[dict]           # [{action, result, is_error}] appended by execute_action
    iteration_count: int                 # incremented by plan_action
    llm_response: str                    # latest raw model reply (action or FINAL ANSWER)
    tokens_input: int                    # accumulated prompt tokens
    tokens_output: int                   # accumulated completion tokens
    charts: list[str]                    # Plotly figure JSON strings captured in execute_action

    # Output
    answer: str | None                   # final markdown answer (FINAL ANSWER stripped)
    selector_reasoning: str | None       # C19 selector rationale (persisted on the run)

    # Control
    error: str | None                    # set by any node on fatal failure -> handle_error
    error_message: str | None            # informational (e.g. "max_iterations") from force_finalize
    status: str                          # running | completed | failed
    max_iterations: int                  # per-run cap (from settings or override)
