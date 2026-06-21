from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Coroutine[Any, Any, Any]]
    category: str = "internal"  # data | service | compute | internal


# Register tools here. The executor adds project-specific tools.
TOOL_REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> Tool:
    TOOL_REGISTRY[tool.name] = tool
    return tool
