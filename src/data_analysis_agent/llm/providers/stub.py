import json
import re

from data_analysis_agent.llm.providers.base import LLMProvider
from data_analysis_agent.llm.types import LLMResult


class StubLLMProvider(LLMProvider):
    """Offline stub — returns plausibly shaped output without any API call."""

    def complete(self, prompt: str) -> LLMResult:
        """Return canned output shaped by the node tag embedded in the prompt.

        Args:
            prompt: The prompt whose ``<node:...>`` tag selects the response shape.

        Returns:
            A zero-cost :class:`LLMResult` mimicking a real provider's reply.
        """
        if "<node:describe_tool>" in prompt:
            text = _describe_tool_reply(prompt)
        elif "<node:plan_action>" not in prompt:
            text = "(stub) No response — unrecognized node tag in prompt."
        else:
            text = _plan_action_reply(prompt)
        return LLMResult(text=text, input_tokens=0, output_tokens=0, total_tokens=0, estimated_cost_usd=0.0)


def _describe_tool_reply(prompt: str) -> str:
    """Build a stub dataset-description response: one tool_description + a per-table capability map."""
    name_match = re.search(r"Dataset name:\s+(.+)", prompt)
    name = name_match.group(1).strip() if name_match else "dataset"
    tables = re.findall(r"Table:\s+(\w+)", prompt)
    return json.dumps({
        "tool_description": f"(stub) Dataset '{name}' available for SQL analysis.",
        "capabilities": {t: f"(stub) Query the '{t}' table." for t in tables},
    })


def _plan_action_reply(prompt: str) -> str:
    """Build a stub plan_action response: a count query on the first capability, then a final answer.

    Emits the two-level call {tool=dataset, capability=table}. Picks the first advertised dataset
    and its first table capability (deterministic — tests should not assume a specific table).
    """
    if "[1] tool:" in prompt:
        return (
            "FINAL ANSWER: (stub) Based on the query results, the data analysis is complete. "
            "Set DATAANALYSIS_OPENROUTER_API_KEY to get real AI-powered answers."
        )
    dataset_match = re.search(r"Tool:\s+(.+)", prompt)         # dataset name (may contain spaces)
    capability_match = re.search(r"capability:\s+(\w+)", prompt)  # first table
    dataset = dataset_match.group(1).strip() if dataset_match else "data"
    table = capability_match.group(1) if capability_match else "data"
    query = f"SELECT COUNT(*) as total_rows FROM {table}"
    return json.dumps({"tool": dataset, "capability": table, "arguments": {"query": query}})
