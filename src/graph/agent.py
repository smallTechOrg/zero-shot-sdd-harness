from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import plan, generate_code, execute_code, finalize, handle_error
from graph.edges import after_plan, after_generate_code, after_execute


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("plan", plan)
    g.add_node("generate_code", generate_code)
    g.add_node("execute_code", execute_code)
    g.add_node("finalize", finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("plan")
    g.add_conditional_edges(
        "plan", after_plan,
        {"generate_code": "generate_code", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "generate_code", after_generate_code,
        {"execute_code": "execute_code", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "execute_code", after_execute,
        {"finalize": "finalize", "generate_code": "generate_code",
         "handle_error": "handle_error"},
    )
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


agentic_ai = _build_graph()
