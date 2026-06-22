from data_analyst.graph.state import AgentState


def after_plan(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "generate_sql"


def after_generate_sql(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "execute_sql"


def after_execute_sql(state: AgentState) -> str:
    if state.get("error") and state.get("retried"):
        return "handle_error"
    if state.get("error"):
        return "generate_sql"  # single regenerate-and-retry
    return "summarize"


def after_summarize(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "finalize"
