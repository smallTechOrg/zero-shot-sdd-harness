from datachat.llm.providers.base import LLMProvider, LLMResponse

_ITERATION_COUNTERS: dict[str, int] = {}


class StubProvider(LLMProvider):
    """Deterministic stub — branches on <node:plan> tag injected by plan_action node."""

    @property
    def name(self) -> str:
        return "stub"

    def generate(self, prompt: str) -> LLMResponse:
        if "<node:plan>" in prompt:
            # After 1 fake action, return FINAL ANSWER
            if "action_history" in prompt and "df." in prompt:
                text = "FINAL ANSWER: [stub] The result is 42."
            else:
                text = "df.describe()"
        else:
            text = "[stub response]"
        return LLMResponse(text=text, tokens_input=10, tokens_output=10)
