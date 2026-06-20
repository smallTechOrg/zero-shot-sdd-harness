"""SSE streaming — keyless test of the step/done event stream."""
from langchain_core.messages import AIMessage

from agent.runner import stream_agent
from agent.sessions import load_resource, release_session


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


async def test_stream_emits_steps_and_done():
    sid = "stream-sess"
    load_resource(sid, "month,revenue\nJan,45000\nFeb,38000\n")
    scripted = [
        AIMessage(content="", tool_calls=[{"name": "inspect_data", "args": {}, "id": "a"}]),
        AIMessage(content="", tool_calls=[{"name": "finish", "args": {"answer": "Revenue data loaded."}, "id": "b"}]),
    ]
    events = [ev async for ev in stream_agent("What is in the dataset?", model=_Fake(scripted), session_id=sid)]
    release_session(sid)
    assert any(e["event"] == "step" for e in events), f"expected step events, got {events}"
    done = [e for e in events if e["event"] == "done"]
    assert done and done[0]["answer"], f"expected a done event with an answer, got {events}"
