from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    tokens_input: int = 0
    tokens_output: int = 0


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> LLMResponse:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...
