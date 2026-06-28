"""Assemble the Local Data Analyst LangGraph (see spec/agent.md ## Graph Assembly)."""
from langgraph.graph import END, StateGraph

from graph.edges import after_execute, after_guard, after_phrase, after_plan
from graph.nodes import (
    execute_sql,
    finalize,
    generate_sql,
    handle_error,
    phrase_answer,
    pick_chart,
    plan,
    privacy_guard,
)
from graph.state import AnalystState


def _build_graph():
    graph = StateGraph(AnalystState)

    graph.add_node("plan", plan)
    graph.add_node("privacy_guard", privacy_guard)
    graph.add_node("generate_sql", generate_sql)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("phrase_answer", phrase_answer)
    graph.add_node("pick_chart", pick_chart)
    graph.add_node("finalize", finalize)
    graph.add_node("handle_error", handle_error)

    graph.set_entry_point("plan")

    graph.add_conditional_edges(
        "plan",
        after_plan,
        {"handle_error": "handle_error", "privacy_guard": "privacy_guard"},
    )
    graph.add_conditional_edges(
        "privacy_guard",
        after_guard,
        {
            "handle_error": "handle_error",
            "execute_sql": "execute_sql",
            "phrase_answer": "phrase_answer",
        },
    )
    graph.add_conditional_edges(
        "execute_sql",
        after_execute,
        {
            "generate_sql": "generate_sql",
            "handle_error": "handle_error",
            "privacy_guard": "privacy_guard",
        },
    )
    graph.add_edge("generate_sql", "execute_sql")
    graph.add_conditional_edges(
        "phrase_answer",
        after_phrase,
        {"handle_error": "handle_error", "pick_chart": "pick_chart"},
    )
    graph.add_edge("pick_chart", "finalize")
    graph.add_edge("finalize", END)
    graph.add_edge("handle_error", END)

    return graph.compile()


agentic_ai = _build_graph()
