import google.generativeai as genai


class GeminiProvider:
    DEFAULT_MODEL = "gemini-2.0-flash"

    def __init__(self, api_key: str, model: str) -> None:
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model or self.DEFAULT_MODEL)

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        full = f"{system}\n\n{prompt}" if system else prompt
        response = self._model.generate_content(full)
        return response.text
