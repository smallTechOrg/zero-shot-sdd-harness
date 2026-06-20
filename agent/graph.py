from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from .config import get_settings
from .observability import span
from .state import AgentState
from .tools import FINISH, TOOL_MAP, TOOLS


def build_graph(model, checkpointer=None):
    bound = model.bind_tools(TOOLS)
    settings = get_settings()

    async def agent_node(state):
        async with span(state["run_id"], f"chat {settings.llm_model}", "LLM") as sp:
            resp = await bound.ainvoke(state["messages"])
            if (u := getattr(resp, "usage_metadata", None)):
                sp["tokens"] = {
                    "input":  u.get("input_tokens", 0) if isinstance(u, dict) else getattr(u, "input_tokens", 0),
                    "output": u.get("output_tokens", 0) if isinstance(u, dict) else getattr(u, "output_tokens", 0),
                }
        return {"messages": state["messages"] + [resp], "iterations": state["iterations"] + 1}

    async def tools_node(state):
        from .guardrails import requires_approval
        out = []
        for tc in state["messages"][-1].tool_calls:
            if tc["name"] == FINISH:
                continue
            if requires_approval(tc["name"]):                       # HITL: pause sensitive actions
                async with span(state["run_id"], f"hitl.{tc['name']}", "INTERNAL") as sp:
                    sp["blocked"], sp["reason"] = True, "requires human approval"
                out.append(ToolMessage(
                    content=f"⏸ '{tc['name']}' is a sensitive, irreversible action and requires human approval. It was NOT performed. Re-run with approval to confirm.",
                    tool_call_id=tc["id"]))
                continue
            tool = TOOL_MAP.get(tc["name"])
            async with span(state["run_id"], f"execute_tool.{tc['name']}", "TOOL", args=tc["args"]) as sp:
                try:
                    if not tool:
                        result = f"unknown tool: {tc['name']}"
                    elif getattr(tool, "coroutine", None) is not None:
                        result = await tool.ainvoke(tc["args"])
                    else:
                        result = tool.invoke(tc["args"])
                except Exception as exc:
                    result = f"tool '{tc['name']}' failed: {type(exc).__name__}: {exc}"
                    sp["error"] = result
                sp["result_preview"] = str(result)[:300]
            out.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
        return {"messages": state["messages"] + out}

    async def finalize_node(state):
        msgs = state["messages"]
        answer = None
        for m in reversed(msgs):
            for tc in getattr(m, "tool_calls", None) or []:
                if tc["name"] == FINISH and tc["args"].get("answer"):
                    answer = tc["args"]["answer"]
                    break
            if answer:
                break
        if not answer:
            raw = getattr(msgs[-1], "content", None)
            if isinstance(raw, list):
                raw = "\n".join(p["text"] for p in raw if isinstance(p, dict) and p.get("type") == "text") or None
            answer = raw or None
        if not answer:
            last_tool = next((m for m in reversed(msgs) if isinstance(m, ToolMessage) and m.content), None)
            if last_tool:
                code_snippet = ""
                for m in reversed(msgs):
                    for tc in getattr(m, "tool_calls", None) or []:
                        if tc["name"] == "python_exec" and tc["args"].get("code"):
                            code_snippet = f"\n\n```python\n{tc['args']['code']}\n```"
                            break
                    if code_snippet:
                        break
                answer = "Ran out of steps — here is what I gathered:\n\n" + str(last_tool.content) + code_snippet
        return {"answer": answer or "(no answer produced)"}

    def route(state):
        if state["iterations"] >= settings.max_iterations:
            return "finalize"
        tcs = getattr(state["messages"][-1], "tool_calls", None)
        if tcs:
            return "finalize" if any(t["name"] == FINISH for t in tcs) else "tools"
        return "finalize"

    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tools_node)
    g.add_node("finalize", finalize_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route, {"tools": "tools", "finalize": "finalize"})
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)
