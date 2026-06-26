from graph.state import AgentState


def after_parse_csv(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "answer_question"


def after_answer_question(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "finalize"
