from langgraph.graph import StateGraph, END

from data_analysis_agent.graph.state import AgentState
from data_analysis_agent.graph.nodes import load_data, plan_query, execute_query, finalize, handle_error
from data_analysis_agent.graph.edges import (
    route_after_load, route_after_plan, route_after_execute, route_after_finalize,
)


def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("load_data", load_data)
    g.add_node("plan_query", plan_query)
    g.add_node("execute_query", execute_query)
    g.add_node("finalize", finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("load_data")

    g.add_conditional_edges(
        "load_data", route_after_load,
        {"plan_query": "plan_query", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "plan_query", route_after_plan,
        {"execute_query": "execute_query", "finalize": "finalize", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "execute_query", route_after_execute,
        {"plan_query": "plan_query", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "finalize", route_after_finalize,
        {"end": END, "handle_error": "handle_error"},
    )
    g.add_edge("handle_error", END)

    return g.compile()


agent_graph = _build_graph()
