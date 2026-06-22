from langgraph.graph import END, StateGraph

from data_analyst.graph.edges import (
    after_execute_sql,
    after_generate_sql,
    after_plan,
    after_summarize,
)
from data_analyst.graph.nodes import (
    node_execute_sql,
    node_finalize,
    node_generate_sql,
    node_handle_error,
    node_plan,
    node_summarize,
)
from data_analyst.graph.state import AgentState


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("plan", node_plan)
    g.add_node("generate_sql", node_generate_sql)
    g.add_node("execute_sql", node_execute_sql)
    g.add_node("summarize", node_summarize)
    g.add_node("finalize", node_finalize)
    g.add_node("handle_error", node_handle_error)

    g.set_entry_point("plan")
    g.add_conditional_edges(
        "plan", after_plan,
        {"generate_sql": "generate_sql", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "generate_sql", after_generate_sql,
        {"execute_sql": "execute_sql", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "execute_sql", after_execute_sql,
        {
            "summarize": "summarize",
            "generate_sql": "generate_sql",
            "handle_error": "handle_error",
        },
    )
    g.add_conditional_edges(
        "summarize", after_summarize,
        {"finalize": "finalize", "handle_error": "handle_error"},
    )
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


compiled_graph = _build_graph()
