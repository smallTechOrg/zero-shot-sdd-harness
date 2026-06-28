from dataclasses import dataclass

from google import genai
from google.genai import types

# Gemini 3.1 Pro public per-1k-token pricing (USD). Used to derive a per-call
# cost from the real token usage the API returns. Kept here so the cost figure
# is documented and easy to update.
_INPUT_USD_PER_1K = 0.00125
_OUTPUT_USD_PER_1K = 0.005


@dataclass
class LLMResult:
    """A model call's text plus the real token usage and derived cost."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


def _cost_for(prompt_tokens: int, completion_tokens: int) -> float:
    return round(
        (prompt_tokens / 1000.0) * _INPUT_USD_PER_1K
        + (completion_tokens / 1000.0) * _OUTPUT_USD_PER_1K,
        6,
    )


class GeminiProvider:
    DEFAULT_MODEL = "gemini-3.1-pro-preview"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    @property
    def model(self) -> str:
        return self._model

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        """Back-compat: text only."""
        return self.call_model_usage(prompt, system=system).text

    def call_model_usage(self, prompt: str, *, system: str | None = None) -> LLMResult:
        """Call the model and return text + real token usage + derived cost."""
        config = (
            types.GenerateContentConfig(system_instruction=system) if system else None
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        return LLMResult(
            text=response.text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=_cost_for(prompt_tokens, completion_tokens),
        )
