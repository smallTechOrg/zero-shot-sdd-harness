from data_analyst.llm.providers.base import LLMProvider


class GeminiProvider(LLMProvider):
    """Google Gemini provider via the official `google-genai` SDK."""

    name = "gemini"

    def __init__(self, api_key: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)

    def complete(self, prompt: str, *, model: str) -> str:
        response = self._client.models.generate_content(
            model=model, contents=prompt
        )
        return (response.text or "").strip()
