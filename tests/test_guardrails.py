"""Guardrails (PII masking) + HITL (human-approval gate) — keyless tests."""
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.graph import build_graph
from agent.guardrails import hitl_approved, scan_pii
from agent.memory import recall, remember


class _Fake:
    def __init__(self, scripted):
        self.s = list(scripted)
        self.i = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, msgs):
        m = self.s[min(self.i, len(self.s) - 1)]
        self.i += 1
        return m


def _delete_then_finish():
    return [
        AIMessage(content="", tool_calls=[{"name": "delete_memories", "args": {}, "id": "d"}]),
        AIMessage(content="", tool_calls=[{"name": "finish", "args": {"answer": "done"}, "id": "f"}]),
    ]


def _state(rid):
    return {"messages": [SystemMessage(content="x"), HumanMessage(content="delete everything")],
            "iterations": 0, "answer": None, "chart": None, "run_id": rid}


def test_pii_guardrail_masks_email():
    v = scan_pii("Reach me at alice@example.com any time.")
    assert v.action == "transform"
    assert "alice@example.com" not in v.payload


async def test_hitl_blocks_risky_without_approval():
    await remember("keep me")
    await build_graph(_Fake(_delete_then_finish())).ainvoke(_state("hitl-block"), config={"recursion_limit": 50})
    assert await recall(), "HITL: a risky action must NOT run without approval"


async def test_hitl_allows_with_approval():
    await remember("delete me")
    token = hitl_approved.set(True)
    try:
        await build_graph(_Fake(_delete_then_finish())).ainvoke(_state("hitl-allow"), config={"recursion_limit": 50})
    finally:
        hitl_approved.reset(token)
    assert not await recall(), "with approval, the risky action executes"
