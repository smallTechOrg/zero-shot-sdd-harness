"""Conditional-edge routers for the ReAct graph.

Mirrors the table in `spec/agent.md` -> "## Graph / Flow Topology". Each function
returns the name of the next node; the graph maps those names to targets in
`agent.py`.
"""
from __future__ import annotations

from graph.state import AgentState

# 3 consecutive execution errors force a wrap-up (kept in sync with nodes.py).
_MAX_CONSECUTIVE_ERRORS = 3
_FINAL_MARKER = "final answer:"


def after_setup(state: AgentState) -> str:
    """setup -> handle_error on fatal load error, else plan_action."""
    if state.get("error"):
        return "handle_error"
    return "plan_action"


def after_plan(state: AgentState) -> str:
    """plan_action -> handle_error / finalize / execute_action."""
    if state.get("error"):
        return "handle_error"
    llm_response = (state.get("llm_response") or "").lower()
    if _FINAL_MARKER in llm_response:
        return "finalize"
    return "execute_action"


def _consecutive_errors(action_history: list[dict]) -> int:
    count = 0
    for step in reversed(action_history):
        if step.get("is_error"):
            count += 1
        else:
            break
    return count


def after_execute(state: AgentState) -> str:
    """execute_action -> handle_error / force_finalize / plan_action.

    force_finalize fires on 3 consecutive `is_error` OR `iteration_count >= max_iterations`.
    A recoverable execution error simply loops back to plan_action to self-correct.
    """
    if state.get("error"):
        return "handle_error"

    action_history = state.get("action_history") or []
    iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 6)

    if _consecutive_errors(action_history) >= _MAX_CONSECUTIVE_ERRORS:
        return "force_finalize"
    if iteration >= max_iterations:
        return "force_finalize"
    return "plan_action"
