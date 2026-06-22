from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    load_schema,
    generate_sql,
    execute_sql,
    format_answer,
    handle_error,
    finalize,
)
from graph.edges import route


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("load_schema", load_schema)
    g.add_node("generate_sql", generate_sql)
    g.add_node("execute_sql", execute_sql)
    g.add_node("format_answer", format_answer)
    g.add_node("handle_error", handle_error)
    g.add_node("finalize", finalize)
    g.set_entry_point("load_schema")
    for src, nxt in [
        ("load_schema", "generate_sql"),
        ("generate_sql", "execute_sql"),
        ("execute_sql", "format_answer"),
        ("format_answer", "finalize"),
    ]:
        g.add_conditional_edges(src, route(nxt), {nxt: nxt, "handle_error": "handle_error"})
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


agentic_ai = _build_graph()
