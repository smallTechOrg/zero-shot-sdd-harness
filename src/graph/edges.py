"""Conditional-edge routing functions for the data-analysis graph.

See spec/agent.md "Graph / Flow Topology". The bounded retry loop lives in
``after_execute``: an execution error routes back to ``generate_code`` while
attempts remain, otherwise to ``handle_error``.
"""
from graph.state import AgentState
from config.settings import get_settings


def after_load(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "generate_code"


def after_generate(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "execute_code"


def after_execute(state: AgentState) -> str:
    if state.get("exec_error"):
        max_retries = get_settings().max_code_retries
        if state.get("attempts", 0) < max_retries:
            return "generate_code"      # bounded retry
        return "handle_error"
    return "write_answer"


def after_answer(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "finalize"
