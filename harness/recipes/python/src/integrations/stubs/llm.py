"""Stub LLM — returns believable canned responses. No API key required.

Phase 2 gate must pass with APPNAME_LLM_PROVIDER=stub.
Replace with a real provider in Phase 3.
"""

import json
from typing import Any


class StubLLMClient:
    # Rotate through canned plans to simulate a ReAct loop.
    _calls: int = 0

    async def complete(self, messages: list[dict]) -> dict[str, Any]:
        self._calls += 1

        # After 2 tool calls, return a final answer.
        tool_results = [m for m in messages if m.get("role") == "tool"]
        if len(tool_results) >= 2:
            return {
                "tool": "FINAL_ANSWER",
                "result": "[STUB] Analysis complete. Replace with real LLM in Phase 3.",
            }

        # First call — return a plausible tool invocation.
        return {
            "tool": "example_tool",
            "parameters": {"query": "stub query"},
            "reasoning": "[STUB] This is a simulated tool call for Phase 2 testing.",
        }
