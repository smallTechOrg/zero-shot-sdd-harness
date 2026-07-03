from google import genai
from google.genai import types


class GeminiProvider:
    # Spec/agent.md names "gemini-3.1-pro"; the live API exposes that family as
    # "gemini-3.1-pro-preview" (the bare id 404s). Use the real, available id.
    DEFAULT_MODEL = "gemini-3.1-pro-preview"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
        ) if system else None
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        return response.text
