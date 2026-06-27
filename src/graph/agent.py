from langgraph.graph import StateGraph, END

from graph.state import DataAnalysisState
from graph.nodes import (
    parse_upload,
    run_preset_analysis,
    run_nl_query,
    format_response,
    handle_error,
    finalize,
)
from graph.edges import after_parse_and_route, after_preset, after_nl_query


def _build_graph() -> StateGraph:
    g = StateGraph(DataAnalysisState)

    g.add_node("parse_upload", parse_upload)
    g.add_node("run_preset_analysis", run_preset_analysis)
    g.add_node("run_nl_query", run_nl_query)
    g.add_node("format_response", format_response)
    g.add_node("handle_error", handle_error)
    g.add_node("finalize", finalize)

    g.set_entry_point("parse_upload")

    g.add_conditional_edges(
        "parse_upload",
        after_parse_and_route,
        {
            "run_preset_analysis": "run_preset_analysis",
            "run_nl_query": "run_nl_query",
            "handle_error": "handle_error",
        },
    )

    g.add_conditional_edges(
        "run_preset_analysis",
        after_preset,
        {
            "format_response": "format_response",
            "handle_error": "handle_error",
        },
    )

    g.add_conditional_edges(
        "run_nl_query",
        after_nl_query,
        {
            "format_response": "format_response",
            "handle_error": "handle_error",
        },
    )

    g.add_edge("format_response", "finalize")
    g.add_edge("handle_error", "finalize")
    g.add_edge("finalize", END)

    return g.compile()


agentic_ai = _build_graph()
