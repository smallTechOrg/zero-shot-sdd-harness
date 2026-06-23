from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    transform_text,
    generate_sql,
    validate_sql,
    execute_sql,
    format_answer,
    handle_error,
    finalize,
)
from graph.edges import after_transform, gate


def _build_graph() -> StateGraph:
    """Skeleton transform graph (kept for /runs and existing tests)."""
    g = StateGraph(AgentState)
    g.add_node("transform_text", transform_text)
    g.add_node("handle_error", handle_error)
    g.add_node("finalize", finalize)
    g.set_entry_point("transform_text")
    g.add_conditional_edges(
        "transform_text",
        after_transform,
        {"finalize": "finalize", "handle_error": "handle_error"},
    )
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


def _build_analyst_graph() -> StateGraph:
    g = StateGraph(AgentState)
    for name, fn in [
        ("generate_sql", generate_sql),
        ("validate_sql", validate_sql),
        ("execute_sql", execute_sql),
        ("format_answer", format_answer),
        ("finalize", finalize),
        ("handle_error", handle_error),
    ]:
        g.add_node(name, fn)

    g.set_entry_point("generate_sql")
    g.add_conditional_edges(
        "generate_sql",
        gate("validate_sql"),
        {"validate_sql": "validate_sql", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "validate_sql",
        gate("execute_sql"),
        {"execute_sql": "execute_sql", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "execute_sql",
        gate("format_answer"),
        {"format_answer": "format_answer", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "format_answer",
        gate("finalize"),
        {"finalize": "finalize", "handle_error": "handle_error"},
    )
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


agentic_ai = _build_graph()
analyst_graph = _build_analyst_graph()
