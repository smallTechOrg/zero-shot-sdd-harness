from datachat.llm.providers.base import LLMProvider


class StubLLMProvider(LLMProvider):
    """Deterministic stub — branches on <node:query> tag injected by pipeline nodes."""

    def generate(self, prompt: str) -> str:
        if "<node:query>" in prompt:
            return (
                "**Stub answer (no Gemini API key set)**\n\n"
                "Based on the uploaded CSV data, here is a stub response. "
                "To get real answers, set the GEMINI_API_KEY environment variable.\n\n"
                "This stub confirms the pipeline is wired correctly end-to-end."
            )
        return "Stub response: unrecognised node tag."
