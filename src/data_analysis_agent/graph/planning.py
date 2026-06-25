from __future__ import annotations

import json

from data_analysis_agent.graph.state import AgentState

# Prompt tag the stub provider branches on — must not change without updating stub.py.
_PLAN_TAG = "<node:plan_action>"


def build_plan_prompt(state: AgentState, servers: list[dict]) -> str:
    """Assemble the full plan_action prompt for the current ReAct turn.

    The available-tools block is flat: one tool per MCP server (single-level addressing). ``servers``
    is the snapshot from the ``SessionPoolManager`` (not stored in state). Includes the durable
    conversation memory, the question, prior tool-call history, and the single-level response format.

    Args:
        state: The current agent state carrying the question and history.
        servers: Flat tool list ``[{tool, description, tables:[{table, columns}]}]``.

    Returns:
        The complete prompt string sent to the LLM.
    """
    lines = _intro_lines()
    lines += _conversation_lines(state.get("conversation", []))
    lines += _tools_lines(servers)
    lines.append(f"User question: {state['question']}")
    lines += _history_lines(state.get("action_history", []))
    lines += _response_format_lines()
    return "\n".join(lines)


def _conversation_lines(conversation: list[dict]) -> list[str]:
    """Return the durable per-session memory block, or empty when there is none."""
    if not conversation:
        return []
    lines = ["Conversation so far (prior questions and answers in this session):"]
    for i, turn in enumerate(conversation, 1):
        lines.append(f'[{i}] Q: {turn.get("question", "")}')
        lines.append(f'    A: {turn.get("answer", "")}')
    lines.append("")
    return lines


def _intro_lines() -> list[str]:
    """Return the static ReAct-loop introduction and DuckDB dialect notes."""
    return [
        _PLAN_TAG,
        "You are a data-analysis agent operating in a ReAct (Reason + Act) loop.",
        "On each turn you either (a) call a tool to run SQL and gather more data, or (b) give the",
        "final answer. After each call you will see its result and may call another. Build up a plan",
        "across multiple queries — and across multiple tools — until you can answer.",
        "",
        "SQL dialect: DuckDB. Notes:",
        "- Aggregates available natively: COUNT, SUM, AVG, MIN, MAX, STDDEV, VARIANCE, MEDIAN, QUANTILE.",
        "- Use SQRT/ABS/ROUND for math.",
        "- Only SELECT statements are permitted.",
        "- If a column is numeric but stored as text, CAST(col AS DOUBLE) before aggregating.",
        "",
    ]


def _tools_lines(servers: list[dict]) -> list[str]:
    """Return the flat available-tools block (one tool per MCP server)."""
    if not servers:
        return []
    lines = [
        "Available tools. Each tool is an MCP server backed by a dataset; pick one and write SQL.",
        "A query may JOIN any of that server's tables (they share one connection).",
        "",
    ]
    for srv in servers:
        lines.append(f"Tool: {srv['tool']}")
        if srv.get("description"):
            lines.append(f"  {srv['description']}")
        tables = srv.get("tables", [])
        if tables:
            lines.append("  Tables:")
            for t in tables:
                cols = ", ".join(t.get("columns") or [])
                lines.append(f"    {t['table']}({cols})")
        lines.append("")
    return lines


def _history_lines(history: list[dict]) -> list[str]:
    """Return the prior tool-call trace, or an empty list when there is no history."""
    if not history:
        return []
    lines = ["", "Previous tool calls and results:"]
    for i, entry in enumerate(history, 1):
        lines.append(f'[{i}] tool: {entry["tool"]}')
        lines.append(f'    arguments: {json.dumps(entry["arguments"])}')
        if entry.get("is_error"):
            lines.append(f'    result: Error: {entry["result"]}')
            lines.append("    → This call failed. Please write a corrected query.")
        else:
            lines.append(f'    result:\n{entry["result"]}')
    return lines


def _response_format_lines() -> list[str]:
    """Return the closing instructions that define the tool-call / FINAL ANSWER format."""
    return [
        "",
        "Decide your next step. Respond with EXACTLY ONE of the following, and nothing else",
        "(no explanations, no markdown, no backticks):",
        "",
        "1. A JSON tool call to gather more data:",
        '   {"tool": "<server>", "arguments": {"query": "SELECT ..."}}',
        "   ('tool' is one of the server names listed above.)",
        "",
        "2. The final answer, when you have enough information:",
        "   FINAL ANSWER: <your complete answer here>",
    ]
