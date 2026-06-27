from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str              # set at graph entry by run_analysis(); UUID string
    analysis_id: str         # UUID of the AnalysisRow — created before graph, updated by finalize/handle_error

    # Dataset context (populated by ingest_csv or set before graph entry for analysis runs)
    dataset_id: str          # UUID of the DatasetRow in the datasets table
    dataset_path: str        # absolute path: data/uploads/<dataset_id>.csv

    # Input
    question: str            # the user's natural-language question

    # Pipeline data (populated progressively by nodes)
    schema_summary: str      # column names, dtypes, shape, sample rows — built by ingest_csv
    analysis_plan: dict      # parsed JSON from plan_analysis: {pandas_ops, chart_type, chart_columns}
    computed_data: dict      # result of execute_analysis: {result_label: value_or_series, ...}

    # Output (populated by generate_answer and generate_chart)
    answer_text: str         # plain-English answer from generate_answer
    chart_json: str | None   # Plotly figure JSON string from generate_chart; None if no chart

    # Control
    error: str | None        # set by any node on fatal failure; triggers handle_error edge
    status: str              # "pending" | "completed" | "failed"
