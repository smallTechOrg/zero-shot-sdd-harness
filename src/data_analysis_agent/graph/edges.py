from data_analysis_agent.graph.state import AgentState

_FINAL_PREFIX = "FINAL ANSWER:"


def route_after_load(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "plan_query"


def route_after_plan(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    if state.get("llm_response", "").upper().startswith(_FINAL_PREFIX):
        return "finalize"
    return "execute_query"


def route_after_execute(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "plan_query"


def route_after_finalize(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "end"
