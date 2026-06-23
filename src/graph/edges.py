from graph.state import AgentState


def after_transform(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "finalize"


def gate(next_node: str):
    """Conditional edge factory: route to handle_error if state has an error."""

    def _route(state: AgentState) -> str:
        return "handle_error" if state.get("error") else next_node

    return _route
