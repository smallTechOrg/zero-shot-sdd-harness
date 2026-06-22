from data_analyst.config.settings import Settings
from data_analyst.llm.providers.base import LLMProvider
from data_analyst.llm.providers.stub import StubProvider


def create_provider(settings: Settings) -> LLMProvider:
    """Resolve provider from settings. auto -> gemini when key set, else stub."""
    if settings.resolved_llm_provider == "gemini":
        from data_analyst.llm.providers.gemini import GeminiProvider

        return GeminiProvider(api_key=settings.resolved_gemini_api_key)
    return StubProvider()
