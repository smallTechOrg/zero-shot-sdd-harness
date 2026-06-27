from graph.state import DataAnalysisState

_PRESET_TYPES = {"summary_stats", "trend_over_time", "top_bottom_n", "correlation"}


def after_parse_and_route(state: DataAnalysisState) -> str:
    """Route after parse_upload: error → handle_error, nl_query → run_nl_query, else preset."""
    if state.get("error"):
        return "handle_error"
    analysis_type = state.get("analysis_type", "")
    if analysis_type == "nl_query":
        return "run_nl_query"
    return "run_preset_analysis"


def after_preset(state: DataAnalysisState) -> str:
    """Route after run_preset_analysis: error → handle_error, else format_response."""
    if state.get("error"):
        return "handle_error"
    return "format_response"


def after_nl_query(state: DataAnalysisState) -> str:
    """Route after run_nl_query: always error path in Phase 1."""
    if state.get("error"):
        return "handle_error"
    return "format_response"
