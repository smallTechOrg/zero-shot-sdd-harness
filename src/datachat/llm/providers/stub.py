from datachat.llm.providers.base import LLMProvider, LLMResponse


class StubProvider(LLMProvider):
    """
    Deterministic stub — branches on <node:plan> tag injected into the prompt.
    Returns DESCRIPTION/ACTION format on first call, FINAL ANSWER on the second.
    Never branches on prose keywords.
    """

    @property
    def name(self) -> str:
        return "stub"

    def generate(self, prompt: str) -> LLMResponse:
        if "<node:plan>" in prompt:
            # If history already has a step, return a final answer
            if "Step 1:" in prompt:
                text = "FINAL ANSWER: [stub] The computed result is 42."
            else:
                text = (
                    "DESCRIPTION: Checking the summary statistics of the dataset.\n"
                    "ACTION: df.describe()"
                )
        else:
            text = "[stub response]"
        return LLMResponse(text=text, tokens_input=10, tokens_output=10)
