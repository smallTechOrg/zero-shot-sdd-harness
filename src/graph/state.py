from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity ----------------------------------------------------------------
    run_id: str                      # set at initialisation
    dataset_id: str                  # set at initialisation

    # Input -------------------------------------------------------------------
    question: str                    # the user's current question
    messages: list                   # prior turns: [{role, content}] — session memory
    profile: dict                    # schema/dtypes/ranges/quality flags (NO raw rows)

    # Pipeline data (populated progressively) ---------------------------------
    plan: str                        # strategy from `plan` node
    code: str                        # latest generated pandas code
    exec_result: dict                # {result_repr, summary, stdout, error} from executor
    step_index: int                  # current iteration (for step counter)
    max_steps: int                   # bounded loop limit (env AGENT_MAX_STEPS, default 6)
    needs_clarification: bool        # set by `plan` if question is ambiguous
    clarifying_question: str | None

    # Output ------------------------------------------------------------------
    prose: str                       # final prose answer
    chart: dict | None               # chart spec for the frontend
    table: dict | None               # results table (aggregate result only)
    follow_ups: list                 # suggested follow-up questions
    tokens: dict                     # {prompt, completion} cumulative
    cost_usd: float                  # cumulative for this run

    # Control -----------------------------------------------------------------
    error: str | None                # fatal failure → handle_error
    status: str                      # "completed" | "failed" | "needs_clarification"
    _inspect_decision: str           # internal: "refine" | "finish" (inspect → router)
    _forced_finish: bool             # internal: step limit hit → finalize w/ note
