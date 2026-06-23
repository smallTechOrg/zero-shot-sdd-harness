from langgraph.graph import StateGraph, END

from graph.state import AnalystState
from graph.nodes import (
    query_planner,
    sql_executor,
    response_formatter,
    audit_logger,
    handle_error,
    finalize,
)
from graph.edges import after_plan, after_execute


def _build_graph():
    g = StateGraph(AnalystState)

    g.add_node("query_planner", query_planner)
    g.add_node("sql_executor", sql_executor)
    g.add_node("response_formatter", response_formatter)
    g.add_node("audit_logger", audit_logger)
    g.add_node("handle_error", handle_error)
    g.add_node("finalize", finalize)

    g.set_entry_point("query_planner")

    g.add_conditional_edges(
        "query_planner",
        after_plan,
        {"sql_executor": "sql_executor", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "sql_executor",
        after_execute,
        {"response_formatter": "response_formatter", "handle_error": "handle_error"},
    )
    g.add_edge("response_formatter", "audit_logger")
    g.add_edge("audit_logger", "finalize")
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)

    return g.compile()


analyst_graph = _build_graph()
