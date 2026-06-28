from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    dataset_id: str
    csv_paths: dict[str, str]            # {name: local_path} — full file(s); "df" in Phase 1

    # Input (the ONLY things derived for the LLM — see Privacy Boundary)
    question: str
    schema: list[dict]                  # [{name, dtype}]
    sample_rows: list[dict]             # <= 20 sample rows (prompt only)

    # Pipeline data
    plan: str | None
    code: str | None
    attempts: list[dict]                # [{attempt, code, ok, error|null, duration_ms}]
    retries: int
    max_retries: int
    last_error: str | None

    # Output
    answer: str | None
    chart_spec: dict | None
    table: list[dict] | None
    result: object                      # raw computed result payload (for finalize)

    # Telemetry
    tokens: int

    # Control
    error: str | None
    status: str | None
    messages: list
