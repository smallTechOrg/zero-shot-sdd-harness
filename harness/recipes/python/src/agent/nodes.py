import json
import structlog

from src.agent.state import AgentState
from src.agent.tools import TOOL_REGISTRY
from src.integrations.llm import get_llm_client

log = structlog.get_logger()

SYSTEM_PROMPT = """You are a helpful agent. Use the available tools to answer the user's request.

Available tools:
{tools}

Respond with a JSON execution plan:
  {{"tool": "<tool_name>", "parameters": {{...}}, "reasoning": "<why>"}}

Or signal completion:
  {{"tool": "FINAL_ANSWER", "result": "<answer>"}}
"""


async def plan_action(state: AgentState) -> dict:
    client = get_llm_client()
    tools_desc = json.dumps(
        [{"name": t.name, "description": t.description, "parameters": t.parameters}
         for t in TOOL_REGISTRY.values()],
        indent=2,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(tools=tools_desc)},
        {"role": "user", "content": state["user_input"]},
        *state.get("tool_call_history", []),
    ]
    try:
        plan = await client.complete(messages)
        return {
            "tool_call_history": state.get("tool_call_history", []) + [
                {"role": "assistant", "content": json.dumps(plan)}
            ],
            "iterations": state.get("iterations", 0) + 1,
            "result": plan.get("result") if plan.get("tool") == "FINAL_ANSWER" else None,
        }
    except Exception as exc:
        log.error("plan_action_failed", error=str(exc))
        return {"error": f"LLM call failed: {exc}"}


async def invoke_tool(state: AgentState) -> dict:
    history = state.get("tool_call_history", [])
    last = json.loads(history[-1]["content"])
    tool_name = last.get("tool")
    params = last.get("parameters", {})

    tool = TOOL_REGISTRY.get(tool_name)
    if not tool:
        # Recoverable — feed back to plan_action for self-correction
        tool_result = f"Unknown tool: {tool_name!r}. Available: {list(TOOL_REGISTRY)}"
    else:
        try:
            tool_result = await tool.handler(**params)
        except Exception as exc:
            tool_result = f"Tool error: {exc}"

    log.info("tool_invoked", tool=tool_name, result_len=len(str(tool_result)))
    return {
        "tool_call_history": history + [
            {"role": "tool", "content": str(tool_result)}
        ]
    }


async def finalize(state: AgentState) -> dict:
    log.info("run_complete", run_id=state["run_id"], result_len=len(state.get("result", "")))
    return {}


async def handle_error(state: AgentState) -> dict:
    log.error("run_failed", run_id=state["run_id"], error=state.get("error"), iterations=state.get("iterations"))
    return {}
