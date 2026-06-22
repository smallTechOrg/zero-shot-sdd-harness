import json
import re

from data_analyst.llm.providers.base import LLMProvider


class StubProvider(LLMProvider):
    """Offline provider. Branches on explicit <node:...> tags, never on prose.

    Designed so the full pipeline runs end-to-end with zero network I/O and
    produces SQL that actually executes against DuckDB.
    """

    name = "stub"

    def complete(self, prompt: str, *, model: str) -> str:
        if "<node:plan>" in prompt:
            return self._plan(prompt)
        if "<node:generate_sql>" in prompt:
            return self._generate_sql(prompt)
        if "<node:summarize>" in prompt:
            return self._summarize(prompt)
        return "[stub] no node tag recognised"

    def _plan(self, prompt: str) -> str:
        tables = re.findall(r"<table>(.*?)</table>", prompt)
        return json.dumps({"relevant_tables": tables, "complexity": "routine"})

    def _generate_sql(self, prompt: str) -> str:
        tables = re.findall(r"<table>(.*?)</table>", prompt)
        if not tables:
            return "SELECT 1 AS stub_result"
        table = tables[0]
        return f'SELECT count(*) AS row_count FROM "{table}"'

    def _summarize(self, prompt: str) -> str:
        rows = re.findall(r"<result_preview>(.*?)</result_preview>", prompt, re.DOTALL)
        preview = rows[0].strip() if rows else "no rows"
        return (
            "[stub answer] Based on the query result, here is a summary. "
            f"The aggregated result preview was: {preview}. "
            "Set DATA_ANALYST_GEMINI_API_KEY to get a real Gemini-generated answer."
        )
