class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self._api_key = api_key
        self._model = model

    def generate_sql(self, prompt: str) -> str:
        raise RuntimeError("GeminiClient.generate_sql: real implementation in Phase 3")
