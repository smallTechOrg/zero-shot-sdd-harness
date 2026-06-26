"""The provider extension point.

The baseline ships two working providers — Anthropic and Gemini. Adding a
third (e.g. OpenRouter, whose OpenAI-compatible API fronts many models behind
one key, or any other provider) is a ~15-minute extension:

  1. Subclass BaseProvider and implement `call_model`, returning an LLMResponse.
  2. Add the provider's API key to `config/settings.Settings` and wire it in
     `llm/client._make_provider`.
  3. Add the provider's cost tiers to `PRICING` below (or the provider can
     price itself — see AnthropicProvider / GeminiProvider).

Keep the product runtime provider-agnostic: nodes and the graph never import a
concrete provider, only the LLMClient.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from llm.response import LLMResponse


class BaseProvider(ABC):
    """One LLM provider. Concrete providers price their own responses so a
    routed (non-default) model is costed at its real tier — see PRICING."""

    DEFAULT_MODEL: str = ""

    @abstractmethod
    def call_model(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        """Call the model and return a typed LLMResponse.

        `model` overrides the provider's configured/default model for this one
        call (this is what the router uses for per-task model selection). A
        falsy `model` means "use the provider's configured/default model".
        """
        raise NotImplementedError


# Cost tiers in $/million tokens, keyed by the API-reported model id.
# Pricing is looked up on the model the API SAYS it used, so a routed call is
# always costed at its real tier, on every provider. Unknown models cost 0
# (logged by the provider) rather than crashing a run.
PRICING: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-8": (5.00, 25.00),
    # Gemini
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
}


def price(model: str, tokens_in: int, tokens_out: int) -> float:
    """Cost in USD for a call, priced on the API-reported model id.

    Prefix-matches so dated/suffixed ids (e.g. 'claude-haiku-4-5-20251001')
    resolve to their base tier. Returns 0.0 for an unknown model.
    """
    rate = PRICING.get(model)
    if rate is None:
        for known, known_rate in PRICING.items():
            if model.startswith(known):
                rate = known_rate
                break
    if rate is None:
        return 0.0
    cost_in, cost_out = rate
    return (tokens_in * cost_in + tokens_out * cost_out) / 1_000_000
