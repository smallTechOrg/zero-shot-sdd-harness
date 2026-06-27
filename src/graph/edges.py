from graph.state import AgentState


def _route(state: AgentState, next_node: str) -> str:
    return "handle_error" if state.get("error") else next_node


def after_ingest(state: AgentState) -> str:
    return _route(state, "plan_analysis")


def after_plan(state: AgentState) -> str:
    return _route(state, "execute_analysis")


def after_execute(state: AgentState) -> str:
    return _route(state, "generate_answer")


def after_answer(state: AgentState) -> str:
    return _route(state, "generate_chart")


def after_chart(state: AgentState) -> str:
    return _route(state, "finalize")
