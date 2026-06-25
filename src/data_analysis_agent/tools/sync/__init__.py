"""LLM-driven MCP capability generation (the 5-stage sync pipeline).

``run_sync`` generates a server's tools/resources/prompts from its data + existing capabilities;
``apply_sync_result`` applies the result transactionally (versioned, soft-delete-only).
"""
from data_analysis_agent.tools.sync.pipeline import (
    SyncResult,
    apply_sync_result,
    run_sync,
)

__all__ = ["SyncResult", "apply_sync_result", "run_sync"]
