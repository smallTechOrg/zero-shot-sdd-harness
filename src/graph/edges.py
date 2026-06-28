from config.settings import get_settings
from graph.state import AgentState


def after_plan(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "execute_step"


def cap_hit(state: AgentState) -> bool:
    """True when the step cap is reached while the plan is still incomplete."""
    return state.get("step_count", 0) >= get_settings().max_steps and not state.get(
        "plan_complete"
    )


def step_cap_check(state: AgentState) -> str:
    """Conditional router after execute_step (cost guard).

    - If the cap is hit while the plan is incomplete, route to synthesize_answer
      (best-effort answer, never loops freely). The warning is set by the
      synthesize node, which reads the same condition.
    - If the plan is complete, route to synthesize_answer.
    - Otherwise route to replan.
    """
    if cap_hit(state):
        return "synthesize_answer"
    if state.get("plan_complete"):
        return "synthesize_answer"
    return "replan"


def after_replan(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    if state.get("plan_complete"):
        return "synthesize_answer"
    if state.get("next_code"):
        return "execute_step"
    # No further code and not explicitly complete — finish synthesising.
    return "synthesize_answer"


def after_synthesize(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "suggest_followups"
