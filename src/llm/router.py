"""LLM router — maps cost-tier names to model identifiers.

Tiers: "tools" (fast/cheap), "reason" (capable), "classify" (cheapest).
Each tier reads from AGENT_MODEL_<TIER> env var; falls back to empty string
which signals the provider to use its DEFAULT_MODEL.
"""
from config.settings import get_settings


class ModelRouter:
    def route(self, tier: str) -> str:
        """Return the model override for a given tier, or '' for provider default."""
        s = get_settings()
        mapping = {
            "tools": s.model_tools,
            "reason": s.model_reason,
            "classify": s.model_classify,
        }
        return mapping.get(tier, "")


_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
