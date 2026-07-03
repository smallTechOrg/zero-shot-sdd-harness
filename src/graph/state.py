from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                     # set at initialisation by the runner
    dataset_id: str                 # set at initialisation

    # Input
    question: str                   # set at initialisation (the user's plain-language question)

    # Context (populated by load_context — NEVER the raw rows)
    schema: list[dict]              # [{name, dtype, null_count}, ...]
    sample_rows: list[dict]         # a few example rows for the prompt
    row_count: int                  # exact full-data row count
    data_path: str                  # local file path to the full dataset
    file_format: str                # "csv" | "xlsx" — needed by the executor subprocess

    # Pipeline data (populated progressively)
    code: str                       # generated pandas (generate_code)
    exec_result: dict | None        # aggregated {value, table, columns} (execute_code)
    exec_error: str | None          # execution error, if any (execute_code) — drives retry
    attempts: int                   # generate→execute attempts so far

    # Output (populated by write_answer)
    answer_text: str                # plain-language answer with key numbers
    narrative: str                  # short interpretation
    key_numbers: list[dict]         # [{label, value}, ...]
    chart_spec: dict                # Vega-Lite spec
    table: list[dict]               # summary table rows (== exec_result.table)

    # Control
    error: str | None               # set by any node on fatal failure → handle_error
    status: str                     # "completed" | "failed"
    messages: list                  # chat-turn history (Phase 2; present but unused in Phase 1)
