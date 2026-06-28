from graph.state import AgentState


def after_plan(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "generate_code"


def after_generate_code(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "execute_code"


def after_execute(state: AgentState) -> str:
    """Route after a code attempt.

    - last attempt ok            -> finalize
    - failed & retries < cap     -> generate_code (with last_error fed back)
    - failed & retries >= cap    -> handle_error
    """
    attempts = state.get("attempts", [])
    last_ok = bool(attempts) and attempts[-1].get("ok")
    if last_ok:
        return "finalize"

    retries = state.get("retries", 0)
    max_retries = state.get("max_retries", 3)
    if retries < max_retries:
        return "generate_code"
    return "handle_error"
