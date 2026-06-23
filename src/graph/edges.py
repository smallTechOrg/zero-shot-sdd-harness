from graph.state import AnalystState


def after_plan(state: AnalystState) -> str:
    return "handle_error" if state.get("error") else "sql_executor"


def after_execute(state: AnalystState) -> str:
    return "handle_error" if state.get("error") else "response_formatter"
