from typing import TypedDict

# Pipeline constants (see spec/agent.md).
MAX_SQL_RETRIES = 3
AGG_ROW_CAP = 50


class AnalystState(TypedDict, total=False):
    # Identity
    run_id: str                      # set at initialisation (question_runs PK)
    dataset_id: str                  # the profiled dataset being queried

    # Input
    question: str                    # the user's natural-language question
    schema: dict                     # column names + DuckDB types + health summary (NO rows)
    dataset_path: str                # local DuckDB file path
    table_name: str                  # DuckDB table name (default "t")

    # Pipeline data (populated progressively)
    plan: str                        # plan text from the plan node
    sql: str                         # current candidate DuckDB SQL
    sql_attempts: int                # incremented on each execution attempt (cap MAX_SQL_RETRIES)
    sql_error: str | None            # last DuckDB error text (drives retry); None on success
    result: dict                     # {columns, rows} — FULL result, kept local, NOT sent to LLM
    aggregate: dict                  # bounded summary (<= AGG_ROW_CAP) — the ONLY result data sent to LLM
    trace: list                      # [{step, sql?, error?, ok, latency_ms}, ...] — the audit trail
    phase: str                       # "pre" (before execute) | "post" (aggregate built)

    # Output
    answer: str                      # plain-English answer
    key_numbers: list                # the called-out figures
    chart: dict                      # {type, x, y} chosen by pick_chart
    cost_usd: float                  # summed from Gemini token usage this run

    # Control
    error: str | None                # fatal failure (LLM/API/guard) -> handle_error
    status: str                      # "completed" | "failed"
