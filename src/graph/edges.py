"""Conditional-edge routers for the data-analysis graph (see spec/agent.md)."""
from __future__ import annotations

from config.settings import get_settings
from graph.state import AgentState


def route_after_plan(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    if state.get("needs_clarification"):
        return "clarify"
    return "generate_code"


def route_after_generate(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "execute"


def route_after_inspect(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    step = int(state.get("step_index", 0))
    max_steps = int(state.get("max_steps", get_settings().max_steps))
    decision = state.get("_inspect_decision", "finish")
    if decision == "refine" and step < max_steps:
        return "generate_code"
    return "finalize"
