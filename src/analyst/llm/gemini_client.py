import httpx

from analyst.errors import AnalystError

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/{model}:generateContent"
)


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self._model = model
        self._api_key = api_key

    def generate_sql(self, prompt: str) -> str:
        url = _GEMINI_URL.format(model=self._model)
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            resp = httpx.post(url, params={"key": self._api_key}, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except httpx.HTTPStatusError as e:
            raise AnalystError("llm_unavailable", f"Gemini API error: {e.response.status_code} {e.response.text[:200]}", 502)
        except Exception as e:
            raise AnalystError("llm_unavailable", f"Gemini API error: {e}", 502)
