from config.settings import get_settings
from llm.providers.gemini import LLMResult


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


class LLMClient:
    def __init__(self) -> None:
        self._provider = _make_provider()

    @property
    def model(self) -> str:
        return getattr(self._provider, "model", getattr(self._provider, "_model", ""))

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        return self._provider.call_model(prompt, system=system)

    def call_model_usage(self, prompt: str, *, system: str | None = None) -> LLMResult:
        """Call the model and return text + real token usage + derived cost.

        Providers that expose ``call_model_usage`` (Gemini) return real usage;
        others fall back to text-only with zero usage/cost.
        """
        fn = getattr(self._provider, "call_model_usage", None)
        if fn is not None:
            return fn(prompt, system=system)
        text = self._provider.call_model(prompt, system=system)
        return LLMResult(text=text, prompt_tokens=0, completion_tokens=0, cost_usd=0.0)
