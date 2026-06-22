from __future__ import annotations

import sys
from typing import Any


class GeminiClient:
    """Wraps google-generativeai. Falls back to stub when no API key."""

    def __init__(self, api_key: str, model: str) -> None:
        self._model_name = model
        self._stub = not bool(api_key.strip())
        if not self._stub:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self._model = genai.GenerativeModel(model)
            except Exception as exc:
                print(f"Warning: Gemini init failed: {exc}", file=sys.stderr)
                self._stub = True

    def generate_sql(self, prompt: str) -> tuple[str, dict]:
        """Returns (sql_text, token_usage)."""
        if self._stub:
            return "SELECT COUNT(*) AS row_count FROM data", {"input_tokens": 0, "output_tokens": 0, "stub": True}
        try:
            response = self._model.generate_content(prompt)
            usage = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                meta = response.usage_metadata
                usage = {
                    "input_tokens": getattr(meta, "prompt_token_count", 0),
                    "output_tokens": getattr(meta, "candidates_token_count", 0),
                }
            return response.text, usage
        except Exception as exc:
            raise RuntimeError(f"Gemini API error: {exc}") from exc

    def generate_answer(
        self,
        question: str,
        sql: str,
        results_sample: list[dict],
    ) -> str:
        """Generate a prose answer given the question, SQL, and result sample."""
        if self._stub:
            if results_sample:
                return f"Based on the data, here are the results for your question: '{question}'. The query returned {len(results_sample)} row(s)."
            return f"The query for '{question}' returned no results."
        try:
            prompt = (
                f"A user asked: '{question}'\n"
                f"The SQL query was: {sql}\n"
                f"The first few rows of results: {results_sample[:5]}\n"
                f"Write a concise, plain-English answer (2-3 sentences max)."
            )
            response = self._model.generate_content(prompt)
            return response.text
        except Exception as exc:
            return f"I ran the query successfully but could not generate a prose answer: {exc}"


_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    global _client
    if _client is None:
        from data_analyst.config.settings import get_settings
        s = get_settings()
        _client = GeminiClient(api_key=s.gemini_api_key, model=s.gemini_llm_model)
    return _client
