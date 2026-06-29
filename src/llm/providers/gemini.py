from google import genai
from google.genai import types


class GeminiProvider:
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
        ) if system else None
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "quota" in msg.lower() or "rate" in msg.lower():
                raise RuntimeError("Gemini API rate limit reached. Please wait a moment and try again.") from exc
            if "403" in msg or "invalid" in msg.lower() or "api key" in msg.lower():
                raise RuntimeError("Gemini API key is invalid or lacks permissions. Check AGENT_GEMINI_API_KEY in .env.") from exc
            if "timeout" in msg.lower() or "deadline" in msg.lower():
                raise RuntimeError("Gemini API request timed out. Please try again.") from exc
            raise RuntimeError(f"Gemini API error: {msg}") from exc

        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini returned an empty response. The question may have been blocked by safety filters — try rephrasing.")
        return text
