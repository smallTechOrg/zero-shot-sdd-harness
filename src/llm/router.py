"""Model routing — map a logical task to a concrete model id.

Three logical tasks the agent uses:
  - "classify" → cheap/fast model (e.g. Haiku)
  - "tools"    → the tool-use loop model (e.g. Sonnet)
  - "reason"   → hard-reasoning model (e.g. Opus)

The concrete ids live ONLY in .env / settings — never hardcoded in src. A
blank route returns None, which the provider reads as "use your default model".
This keeps the runtime provider-agnostic: the owner sets ids for whichever
provider they configured.
"""
from __future__ import annotations

from config.settings import get_settings

_VALID_TASKS = ("classify", "tools", "reason")


class Router:
    def __init__(self, classify: str = "", tools: str = "", reason: str = "") -> None:
        self._map = {"classify": classify, "tools": tools, "reason": reason}

    def route(self, task: str) -> str | None:
        """Return the configured model id for a task, or None → provider default."""
        if task not in self._map:
            raise ValueError(
                f"Unknown routing task {task!r}. Valid tasks: {_VALID_TASKS}"
            )
        return self._map[task] or None


_router: Router | None = None


def get_router() -> Router:
    global _router
    if _router is None:
        s = get_settings()
        _router = Router(
            classify=s.model_classify,
            tools=s.model_tools,
            reason=s.model_reason,
        )
    return _router


def reset_router() -> None:
    """Test hook — drop the cached router so new settings take effect."""
    global _router
    _router = None
