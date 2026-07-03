from __future__ import annotations

import contextvars

from config.settings import get_settings

# Per-run token accumulation. A ContextVar holding a mutable dict keeps
# concurrent runs isolated: reset_usage() installs a fresh dict in the current
# context, and every LLMClient.call_model() in that same context/thread adds
# its provider's reported usage into that dict. The runner calls reset_usage()
# at the start of a run and get_usage() at the end to roll the totals up.
_usage_var: contextvars.ContextVar[dict] = contextvars.ContextVar("llm_usage")


def _new_accumulator() -> dict:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0}


def reset_usage() -> None:
    """Begin fresh token accumulation for the current run/context."""
    _usage_var.set(_new_accumulator())


def get_usage() -> dict:
    """Return a copy of the current context's usage accumulator."""
    try:
        return dict(_usage_var.get())
    except LookupError:
        return _new_accumulator()


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost from token counts using the configured Gemini pricing.

    This is an ESTIMATE (prices are configurable constants, not billed values).
    """
    s = get_settings()
    cost = (
        input_tokens / 1_000_000 * s.gemini_input_price_per_1m
        + output_tokens / 1_000_000 * s.gemini_output_price_per_1m
    )
    return round(cost, 6)


def _make_provider():
    s = get_settings()
    provider = s.llm_provider

    # auto-detect from whichever key is set
    if not provider:
        if s.anthropic_api_key:
            provider = "anthropic"
        elif s.gemini_api_key:
            provider = "gemini"
        else:
            raise RuntimeError(
                "No LLM provider configured. Set AGENT_ANTHROPIC_API_KEY or "
                "AGENT_GEMINI_API_KEY in .env, or set AGENT_LLM_PROVIDER explicitly."
            )

    if provider == "anthropic":
        from llm.providers.anthropic import AnthropicProvider
        return AnthropicProvider(api_key=s.anthropic_api_key, model=s.llm_model)
    if provider == "gemini":
        from llm.providers.gemini import GeminiProvider
        return GeminiProvider(api_key=s.gemini_api_key, model=s.llm_model)

    raise RuntimeError(f"Unknown LLM provider: {provider!r}. Supported: anthropic, gemini")


def _accumulate(usage: dict | None) -> None:
    """Fold one provider call's usage into the current context's accumulator."""
    if not usage:
        return
    try:
        acc = _usage_var.get()
    except LookupError:
        # No reset_usage() active in this context — nothing to accumulate into.
        return
    acc["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
    acc["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
    acc["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
    acc["calls"] += 1


class LLMClient:
    def __init__(self) -> None:
        self._provider = _make_provider()

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        text = self._provider.call_model(prompt, system=system)
        # Read the provider's last-call usage (if it reported any) and roll it
        # into the current run's accumulator. Missing usage degrades silently.
        _accumulate(getattr(self._provider, "last_usage", None))
        return text
