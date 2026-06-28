from typing import TypedDict


class AgentState(TypedDict, total=False):
    # --- identity / inputs (set by runner) ---
    run_id: str
    question_id: str
    dataset_id: str
    csv_path: str
    schema: list[dict]          # [{name, type}, ...] — sent to LLM
    sample_rows: list[dict]     # ≤ AGENT_SAMPLE_ROWS rows — sent to LLM
    question_text: str
    messages: list              # prior conversation turns (memory) — P4

    # --- planning ---
    plan: list[str]             # ordered analysis steps (text)
    next_code: str | None       # code for the next step to run
    next_language: str          # "sql" | "pandas"
    plan_complete: bool

    # --- execution / cost guard ---
    steps: list[dict]           # [{index, code, language, result, error, latency_ms}]
    step_count: int
    cost_guard_warning: str | None

    # --- cost accounting ---
    tokens_in: int
    tokens_out: int

    # --- answer ---
    answer: str
    key_numbers: list[dict]     # [{label, value}]
    result_table: dict          # {columns, rows} (bounded)
    chart_spec: dict | None     # P3
    followups: list[str]        # P2

    # --- control ---
    error: str | None
    status: str                 # "completed" | "failed"
