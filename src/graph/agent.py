from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    load_context,
    generate_code,
    execute_code,
    write_answer,
    finalize,
    handle_error,
)
from graph.edges import after_load, after_generate, after_execute, after_answer


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("load_context", load_context)
    g.add_node("generate_code", generate_code)
    g.add_node("execute_code", execute_code)
    g.add_node("write_answer", write_answer)
    g.add_node("finalize", finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("load_context")
    g.add_conditional_edges(
        "load_context",
        after_load,
        {"generate_code": "generate_code", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "generate_code",
        after_generate,
        {"execute_code": "execute_code", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "execute_code",
        after_execute,
        {
            "generate_code": "generate_code",   # bounded retry
            "write_answer": "write_answer",
            "handle_error": "handle_error",
        },
    )
    g.add_conditional_edges(
        "write_answer",
        after_answer,
        {"finalize": "finalize", "handle_error": "handle_error"},
    )
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


agentic_ai = _build_graph()
