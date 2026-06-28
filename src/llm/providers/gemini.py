from dataclasses import dataclass

from google import genai
from google.genai import types


@dataclass
class LLMResult:
    """Text plus token usage for one LLM call (used for cost accounting)."""

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class GeminiProvider:
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        return self.generate(prompt, system=system).text

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        json_mode: bool = False,
    ) -> LLMResult:
        """Generate content and return text + token usage.

        When ``json_mode`` is set the model is asked for a JSON object via
        ``response_mime_type`` so callers can parse a structured result.
        """
        config_kwargs: dict = {}
        if system:
            config_kwargs["system_instruction"] = system
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
        completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
        return LLMResult(
            text=response.text or "",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
