from src.config import settings


class BaseLLMClient:
    def complete(self, prompt: str, system: str = "") -> str:
        raise NotImplementedError


class StubLLMClient(BaseLLMClient):
    def complete(self, prompt: str, system: str = "") -> str:
        if "plot" in prompt.lower() or "chart" in prompt.lower():
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
