"""Legacy transform-text agent — kept for /runs endpoint backward compatibility."""
from pathlib import Path

from langgraph.graph import StateGraph, END

from graph.state import AgentState
from llm.client import LLMClient

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "transform.md"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def _transform_text(state: AgentState) -> AgentState:
    try:
        prompt_template = _load_prompt()
        result = LLMClient().call_model(
            f"{prompt_template}\n\nInput: {state['input_text']}"
        )
        return {**state, "output_text": result}
    except Exception as exc:
        return {**state, "error": str(exc)}


def _handle_error(state: AgentState) -> AgentState:
    return {**state, "status": "failed"}


def _finalize(state: AgentState) -> AgentState:
    return {**state, "status": "completed"}


def _after_transform(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "finalize"


def _build_legacy_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("transform_text", _transform_text)
    g.add_node("handle_error", _handle_error)
    g.add_node("finalize", _finalize)
    g.set_entry_point("transform_text")
    g.add_conditional_edges(
        "transform_text",
        _after_transform,
        {"finalize": "finalize", "handle_error": "handle_error"},
    )
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


legacy_agentic_ai = _build_legacy_graph()
