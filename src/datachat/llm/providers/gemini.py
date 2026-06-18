from datachat.llm.providers.base import LLMProvider, LLMResponse


class GeminiProvider(LLMProvider):
    """Google Gemini provider using the `google.genai` SDK (not deprecated google.generativeai)."""

    def __init__(self, api_key: str, model: str) -> None:
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return "gemini"

    def generate(self, prompt: str) -> LLMResponse:
        from google import genai
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
        )
        text = response.text or ""
        tokens_in = 0
        tokens_out = 0
        if response.usage_metadata:
            tokens_in = response.usage_metadata.prompt_token_count or 0
            tokens_out = response.usage_metadata.candidates_token_count or 0
        return LLMResponse(text=text, tokens_input=tokens_in, tokens_output=tokens_out)
