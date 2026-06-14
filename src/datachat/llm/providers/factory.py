from datachat.llm.providers.base import LLMProvider


def create_llm_provider() -> tuple[LLMProvider, bool]:
    """
    Returns (provider, is_stub).
    Auto-selects: real Gemini when GEMINI_API_KEY is set, stub otherwise.
    """
    from datachat.config.settings import get_gemini_settings, get_settings

    gemini_key = get_gemini_settings().gemini_api_key
    if gemini_key:
        from datachat.llm.providers.gemini import GeminiProvider
        model = get_settings().llm_model
        return GeminiProvider(api_key=gemini_key, model=model), False

    from datachat.llm.providers.stub import StubLLMProvider
    return StubLLMProvider(), True
