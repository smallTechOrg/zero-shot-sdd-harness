from google import genai
from google.genai import types

from llm.base import BaseProvider, price
from llm.response import LLMResponse


class GeminiProvider(BaseProvider):
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def call_model(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        used_model = model or self._model
        config = types.GenerateContentConfig(
            system_instruction=system,
        ) if system else None
        response = self._client.models.generate_content(
            model=used_model,
            contents=prompt,
            config=config,
        )
        usage = response.usage_metadata
        tokens_in = usage.prompt_token_count or 0
        tokens_out = usage.candidates_token_count or 0
        # Gemini doesn't echo the model id in the response, so price on the
        # model we requested (which is the routed/override model when set).
        return LLMResponse(
            text=response.text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=used_model,
            cost_usd=price(used_model, tokens_in, tokens_out),
        )
