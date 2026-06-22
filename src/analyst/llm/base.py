from typing import Protocol, runtime_checkable


@runtime_checkable
class GeminiProvider(Protocol):
    def generate_sql(self, prompt: str) -> str: ...
