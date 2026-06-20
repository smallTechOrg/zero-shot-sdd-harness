"""Multi-agent scaffold — OFF by default.

The default grounded assistant runs as a SINGLE ReAct loop, which is enough for one
capability. When a task genuinely can't fit one loop (independent sub-tasks, or a
sub-task that needs its own isolated context), promote to a supervisor + sub-agents:

    from agent.multi_agent import run_subagent
    summary = await run_subagent("Summarize the retrieved passages")

`run_subagent` runs a fresh, isolated agent loop (its own message history) and returns
ONLY its final answer — so the supervisor (the main loop) keeps its context clean. This
mirrors Claude Code's own subagent model (isolated context window, summary returned).

It is intentionally NOT wired into the default capability. Turn it on when a capability
needs it — and bind a new EARS criterion + test for the new behaviour, per the harness rules.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from .graph import build_graph
from .llm import get_model

SUBAGENT_PROMPT = (
    "You are a focused sub-agent. Do exactly the task asked using the tools available, "
    "then call finish with the result. Keep it tight."
)


async def run_subagent(task: str, *, model=None, run_id: str = "subagent") -> str:
    """Run an isolated sub-agent loop and return only its final answer (the supervisor pattern)."""
    model = model or get_model()
    graph = build_graph(model)
    state = {
        "messages": [SystemMessage(content=SUBAGENT_PROMPT), HumanMessage(content=task)],
        "iterations": 0, "answer": None, "run_id": run_id,
    }
    result = await graph.ainvoke(state, config={"recursion_limit": 50})
    return result["answer"]
