from typing import Any

from src.config import get_settings
from src.integrations.stubs.llm import StubLLMClient


class LLMClient:
    """Thin async LLM client. Swap the provider without changing call sites."""

    async def complete(self, messages: list[dict]) -> dict[str, Any]:
        settings = get_settings()
        provider = settings.resolved_llm_provider

        if provider == "stub":
            return await StubLLMClient().complete(messages)

        if provider == "openai":
            from src.integrations._openai import OpenAIClient
            return await OpenAIClient().complete(messages)

        if provider == "anthropic":
            from src.integrations._anthropic import AnthropicClient
            return await AnthropicClient().complete(messages)

        if provider == "gemini":
            from src.integrations._gemini import GeminiClient
            return await GeminiClient().complete(messages)

        raise ValueError(f"Unknown LLM provider: {provider!r}")


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
