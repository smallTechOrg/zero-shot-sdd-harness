from typing import Any
from src.config import get_settings
from src.integrations.stubs.llm import StubLLMClient


class LLMClient:
    async def complete(self, messages: list[dict]) -> dict[str, Any]:
        provider = get_settings().resolved_llm_provider

        if provider == "stub":
            return await StubLLMClient().complete(messages)

        if provider == "gemini":
            from src.integrations._gemini import GeminiClient
            return await GeminiClient().complete(messages)

        raise ValueError(f"Unknown LLM provider: {provider!r} (expected 'stub' or 'gemini')")


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
