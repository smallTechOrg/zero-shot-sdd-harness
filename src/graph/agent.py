"""Graph assembly — the bounded plan→generate→execute→inspect→refine loop.

Compiled without a checkpointer (runs are short-lived; no resume). See
spec/agent.md "Graph Assembly".
"""
from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    node_plan,
    node_clarify,
    node_generate_code,
    node_execute,
    node_inspect,
    node_finalize,
    node_handle_error,
)
from graph.edges import (
    route_after_plan,
    route_after_generate,
    route_after_inspect,
)


def _build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("plan", node_plan)
    graph.add_node("clarify", node_clarify)
    graph.add_node("generate_code", node_generate_code)
    graph.add_node("execute", node_execute)
    graph.add_node("inspect", node_inspect)
    graph.add_node("finalize", node_finalize)
    graph.add_node("handle_error", node_handle_error)

    graph.set_entry_point("plan")

    graph.add_conditional_edges(
        "plan",
        route_after_plan,
        {
            "handle_error": "handle_error",
            "clarify": "clarify",
            "generate_code": "generate_code",
        },
    )
    graph.add_conditional_edges(
        "generate_code",
        route_after_generate,
        {"handle_error": "handle_error", "execute": "execute"},
    )
    graph.add_edge("execute", "inspect")
    graph.add_conditional_edges(
        "inspect",
        route_after_inspect,
        {
            "handle_error": "handle_error",
            "generate_code": "generate_code",  # refine loop
            "finalize": "finalize",
        },
    )
    graph.add_edge("finalize", END)
    graph.add_edge("clarify", END)
    graph.add_edge("handle_error", END)

    return graph.compile()


agentic_ai = _build_graph()
