"""Structured LLM response with usage metadata."""
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    model: str
    latency_ms: float = 0.0
