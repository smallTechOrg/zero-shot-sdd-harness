import anthropic as _sdk


class AnthropicProvider:
    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = _sdk.Anthropic(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        text, _ = self.call_model_with_usage(prompt, system=system)
        return text

    def call_model_with_usage(
        self, prompt: str, *, system: str | None = None
    ) -> tuple[str, int]:
        kwargs: dict = dict(
            model=self._model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system
        msg = self._client.messages.create(**kwargs)
        tokens = 0
        usage = getattr(msg, "usage", None)
        if usage is not None:
            tokens = (getattr(usage, "input_tokens", 0) or 0) + (
                getattr(usage, "output_tokens", 0) or 0
            )
        return msg.content[0].text, tokens
