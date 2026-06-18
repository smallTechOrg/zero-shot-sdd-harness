from datachat.llm.providers.base import LLMProvider


def create_provider() -> LLMProvider:
    from datachat.config.settings import get_settings
    s = get_settings()
    if s.resolved_llm_provider == "gemini":
        from datachat.llm.providers.gemini import GeminiProvider
        return GeminiProvider(api_key=s.gemini_api_key, model=s.llm_model)
    from datachat.llm.providers.stub import StubProvider
    return StubProvider()
