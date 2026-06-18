from datachat.graph.state import AgentState
from datachat.config.settings import get_settings


def after_setup(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "plan_action"


def after_plan_action(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"

    max_iter = get_settings().max_iterations
    if state.get("iteration_count", 0) >= max_iter:
        return "force_finalize"

    raw = state.get("llm_response", "")
    if raw.upper().startswith("FINAL ANSWER:"):
        return "finalize"

    return "execute_action"
