from src.config import settings


class BaseLLMClient:
    def complete(self, prompt: str, system: str = "") -> str:
        raise NotImplementedError


class StubLLMClient(BaseLLMClient):
    def complete(self, prompt: str, system: str = "") -> str:
        # Extract only the user question line so prompt boilerplate doesn't trigger chart intent
        question_line = prompt
        for line in prompt.splitlines():
            if line.lower().startswith("user question:"):
                question_line = line
                break
        if "plot" in question_line.lower() or "chart" in question_line.lower():
            return (
                '{"intent": "chart", '
                '"sql": "SELECT product, SUM(revenue) FROM sales GROUP BY product", '
                '"x_col": "product", "y_col": "SUM(revenue)"}'
            )
        return '{"intent": "table", "sql": "SELECT * FROM sales LIMIT 10"}'


def get_llm_client() -> BaseLLMClient:
    provider = settings.resolved_llm_provider
    if provider == "stub":
        return StubLLMClient()
    raise NotImplementedError(f"Provider {provider!r} not yet implemented")
