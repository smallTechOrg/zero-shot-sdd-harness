from config.settings import get_settings


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
        # The data-analysis agent pins the Gemini model via AGENT_GEMINI_MODEL;
        # fall back to the generic llm_model if explicitly set.
        model = s.gemini_model or s.llm_model
        return GeminiProvider(api_key=s.gemini_api_key, model=model)

    raise RuntimeError(f"Unknown LLM provider: {provider!r}. Supported: anthropic, gemini")


class LLMClient:
    def __init__(self) -> None:
        self._provider = _make_provider()

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        return self._provider.call_model(prompt, system=system)

    def generate(self, prompt: str, *, system: str | None = None, json_mode: bool = False):
        """Return an LLMResult (text + token usage).

        Used by the agent nodes for cost accounting. Providers that don't
        expose usage return zero token counts but still produce text.
        """
        gen = getattr(self._provider, "generate", None)
        if gen is not None:
            return gen(prompt, system=system, json_mode=json_mode)
        # Fallback for providers without usage metadata.
        from llm.providers.gemini import LLMResult
        return LLMResult(text=self._provider.call_model(prompt, system=system))
