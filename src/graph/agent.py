from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import parse_csv, answer_question, handle_error, finalize
from graph.edges import after_parse_csv, after_answer_question


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("parse_csv", parse_csv)
    g.add_node("answer_question", answer_question)
    g.add_node("handle_error", handle_error)
    g.add_node("finalize", finalize)

    g.set_entry_point("parse_csv")

    g.add_conditional_edges(
        "parse_csv",
        after_parse_csv,
        {"answer_question": "answer_question", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "answer_question",
        after_answer_question,
        {"finalize": "finalize", "handle_error": "handle_error"},
    )

    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)

    return g.compile()


agentic_ai = _build_graph()
