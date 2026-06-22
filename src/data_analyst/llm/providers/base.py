from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Minimal text-in/text-out provider interface."""

    name: str

    @abstractmethod
    def complete(self, prompt: str, *, model: str) -> str:
        """Return the model's text response for a single prompt."""
        raise NotImplementedError
