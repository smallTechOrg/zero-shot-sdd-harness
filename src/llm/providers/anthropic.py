import anthropic as _sdk

from llm.base import BaseProvider, price
from llm.response import LLMResponse


class AnthropicProvider(BaseProvider):
    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = _sdk.Anthropic(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def call_model(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        kwargs: dict = dict(
            model=model or self._model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system
        msg = self._client.messages.create(**kwargs)
        tokens_in = msg.usage.input_tokens
        tokens_out = msg.usage.output_tokens
        # Price on the model the API reports it used, so a routed model is
        # costed at its real tier (not the provider's configured default).
        return LLMResponse(
            text=msg.content[0].text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=msg.model,
            cost_usd=price(msg.model, tokens_in, tokens_out),
        )
