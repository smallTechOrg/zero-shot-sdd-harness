from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    plan,
    execute_step,
    replan,
    synthesize_answer,
    suggest_followups,
    handle_error,
    finalize,
)
from graph.edges import after_plan, step_cap_check, after_replan, after_synthesize


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("plan", plan)
    g.add_node("execute_step", execute_step)
    g.add_node("replan", replan)
    g.add_node("synthesize_answer", synthesize_answer)
    g.add_node("suggest_followups", suggest_followups)  # P2; P1 passthrough → finalize
    g.add_node("handle_error", handle_error)
    g.add_node("finalize", finalize)

    g.set_entry_point("plan")
    g.add_conditional_edges(
        "plan",
        after_plan,
        {"execute_step": "execute_step", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "execute_step",
        step_cap_check,
        {"replan": "replan", "synthesize_answer": "synthesize_answer"},
    )
    g.add_conditional_edges(
        "replan",
        after_replan,
        {
            "execute_step": "execute_step",
            "synthesize_answer": "synthesize_answer",
            "handle_error": "handle_error",
        },
    )
    g.add_conditional_edges(
        "synthesize_answer",
        after_synthesize,
        {"suggest_followups": "suggest_followups", "handle_error": "handle_error"},
    )
    g.add_edge("suggest_followups", "finalize")
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


agentic_ai = _build_graph()
