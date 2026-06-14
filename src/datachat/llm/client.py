from datachat.llm.providers.base import LLMProvider
from datachat.llm.providers.factory import create_llm_provider

_provider: LLMProvider | None = None
_is_stub: bool = True


def get_llm_client() -> tuple[LLMProvider, bool]:
    """Returns (provider, is_stub). Lazily initialised singleton."""
    global _provider, _is_stub
    if _provider is None:
        _provider, _is_stub = create_llm_provider()
    return _provider, _is_stub


def reset_llm_client() -> None:
    """Reset for testing."""
    global _provider, _is_stub
    _provider = None
    _is_stub = True
