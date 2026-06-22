from data_analyst.config.settings import Settings, get_settings
from data_analyst.llm.providers.base import LLMProvider
from data_analyst.llm.providers.factory import create_provider
from data_analyst.observability import get_logger

log = get_logger("data_analyst.llm")


class LLMClient:
    """Wrapper around a provider. Nodes call this, never the SDK directly."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._provider: LLMProvider = create_provider(self._settings)

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def default_model(self) -> str:
        return self._settings.llm_model

    @property
    def escalation_model(self) -> str:
        return self._settings.llm_model_escalation

    def model_for(self, complexity: str) -> str:
        return self.escalation_model if complexity == "complex" else self.default_model

    def complete(self, prompt: str, *, model: str | None = None) -> str:
        chosen = model or self.default_model
        log.info("llm.complete", provider=self._provider.name, model=chosen)
        return self._provider.complete(prompt, model=chosen)


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    return LLMClient(settings)
