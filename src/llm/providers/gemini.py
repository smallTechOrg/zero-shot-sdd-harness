from google import genai
from google.genai import types


class GeminiProvider:
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        text, _tokens_in, _tokens_out = self.call_model_with_usage(prompt, system=system)
        return text

    def call_model_with_usage(
        self, prompt: str, *, system: str | None = None
    ) -> tuple[str, int, int]:
        """Return (text, tokens_in, tokens_out) for cost accounting."""
        config = types.GenerateContentConfig(
            system_instruction=system,
        ) if system else None
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        text = response.text or ""
        tokens_in, tokens_out = 0, 0
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            tokens_in = getattr(usage, "prompt_token_count", 0) or 0
            tokens_out = getattr(usage, "candidates_token_count", 0) or 0
        return text, int(tokens_in), int(tokens_out)
