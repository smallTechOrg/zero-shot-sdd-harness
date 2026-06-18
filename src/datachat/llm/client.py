from datachat.llm.providers.base import LLMProvider, LLMResponse

_provider: LLMProvider | None = None


def get_llm_client() -> LLMProvider:
    global _provider
    if _provider is None:
        from datachat.llm.providers.factory import create_provider
        _provider = create_provider()
    return _provider


def generate(prompt: str) -> LLMResponse:
    return get_llm_client().generate(prompt)
