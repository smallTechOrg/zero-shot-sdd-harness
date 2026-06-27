from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Legacy state — kept for backward compatibility with existing runs graph."""
    run_id: str
    input_text: str
    output_text: str
    error: str | None
    messages: list          # [{role: "user"|"assistant", content: str}, ...]


class DataAnalysisState(TypedDict, total=False):
    """State for the Data Analysis agent graph."""
    run_id: str             # analysis_id (UUID)
    upload_id: str
    analysis_type: str      # "summary_stats"|"trend_over_time"|"top_bottom_n"|"correlation"|"nl_query"
    params: dict[str, Any]
    question: str | None    # For nl_query

    # Set by parse_upload
    dataframe: Any          # pandas DataFrame
    filepath: str

    # Set by analysis nodes
    summary: str | None
    chart_json: str | None
    table: list[dict] | None

    # Lifecycle
    status: str | None      # "pending"|"completed"|"failed"
    error: str | None
