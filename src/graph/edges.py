from collections.abc import Callable

from graph.state import AgentState


def route(next_node: str) -> Callable[[AgentState], str]:
    """Conditional-edge helper: go to handle_error if error is set, else next_node."""

    def _router(state: AgentState) -> str:
        if state.get("error"):
            return "handle_error"
        return next_node

    return _router
