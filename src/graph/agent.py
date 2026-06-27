from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    ingest_csv,
    plan_analysis,
    execute_analysis,
    generate_answer,
    generate_chart,
    finalize,
    handle_error,
)
from graph.edges import (
    after_ingest,
    after_plan,
    after_execute,
    after_answer,
    after_chart,
)


def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("ingest_csv", ingest_csv)
    g.add_node("plan_analysis", plan_analysis)
    g.add_node("execute_analysis", execute_analysis)
    g.add_node("generate_answer", generate_answer)
    g.add_node("generate_chart", generate_chart)
    g.add_node("finalize", finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("ingest_csv")

    g.add_conditional_edges(
        "ingest_csv",
        after_ingest,
        {"plan_analysis": "plan_analysis", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "plan_analysis",
        after_plan,
        {"execute_analysis": "execute_analysis", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "execute_analysis",
        after_execute,
        {"generate_answer": "generate_answer", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "generate_answer",
        after_answer,
        {"generate_chart": "generate_chart", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "generate_chart",
        after_chart,
        {"finalize": "finalize", "handle_error": "handle_error"},
    )

    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)

    return g.compile()


agentic_ai = _build_graph()
