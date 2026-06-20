"""Multi-agent scaffold — keyless test that the isolated sub-agent loop works."""
from langchain_core.messages import AIMessage

from agent.multi_agent import run_subagent


class _Fake:
    def bind_tools(self, tools):
        return self

    async def ainvoke(self, msgs):
        return AIMessage(content="", tool_calls=[{"name": "finish", "args": {"answer": "sub-done"}, "id": "f"}])


async def test_subagent_runs_isolated_and_returns_answer():
    assert await run_subagent("do a focused thing", model=_Fake()) == "sub-done"
