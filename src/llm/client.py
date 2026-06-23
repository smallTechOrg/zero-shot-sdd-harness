from config.settings import get_settings


def _make_provider():
    s = get_settings()

    if s.gemini_api_key:
        from llm.providers.gemini import GeminiProvider
        return GeminiProvider(api_key=s.gemini_api_key, model=s.llm_model)

    raise RuntimeError(
        "No LLM provider configured. Set AGENT_GEMINI_API_KEY in .env."
    )


class LLMClient:
    def __init__(self) -> None:
        self._provider = _make_provider()

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        return self._provider.call_model(prompt, system=system)
