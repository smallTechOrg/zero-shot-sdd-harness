from __future__ import annotations

import json
from typing import NamedTuple

import pandas as pd
import structlog

log = structlog.get_logger()

# Prompt tag the stub provider branches on — must not change without updating stub.py.
_DESCRIBE_TAG = "<node:describe_tool>"


class DatasetDescriptions(NamedTuple):
    """A dataset's LLM-generated metadata: one tool description + per-table capability descriptions."""

    tool: str                          # dataset-level tool_description
    capabilities: dict[str, str]       # table_name -> capability_description


def generate_dataset_descriptions(dataset_name: str, tables: list[dict]) -> DatasetDescriptions:
    """Ask the LLM to describe a whole dataset (all its tables); fall back to templates on failure.

    Samples each table's Parquet, prompts the LLM, and parses the JSON reply. Any failure (stub
    mode, network error, malformed JSON, missing file) falls back to deterministic templates so
    upload/sync never fail.

    Args:
        dataset_name: The dataset (tool) name.
        tables: Dicts with ``table_name``, ``schema`` ([{name,dtype,nullable}]), ``row_count``,
            and optionally ``parquet_path`` (for sampling).

    Returns:
        A :class:`DatasetDescriptions` (tool description + ``{table_name: capability_description}``).
    """
    fallback = _fallback(dataset_name, tables)
    try:
        prompt = _build_prompt(dataset_name, tables)
        from data_analysis_agent.llm.client import get_llm_client
        result = get_llm_client().complete(prompt)
        descriptions = _parse(result.text or "", fallback)
        log.info("descriptions.generated", dataset=dataset_name, tables=len(tables))
        return descriptions
    except Exception as exc:
        log.warning("descriptions.fallback", dataset=dataset_name, error=str(exc))
        return fallback


def _fallback(dataset_name: str, tables: list[dict]) -> DatasetDescriptions:
    """Deterministic descriptions used when the LLM call cannot be trusted."""
    names = [t["table_name"] for t in tables]
    tool = f"Dataset '{dataset_name}' with table(s): {', '.join(names) or '(none)'}."
    caps = {
        t["table_name"]: f"Run a SQL SELECT against the '{t['table_name']}' table in dataset '{dataset_name}'."
        for t in tables
    }
    return DatasetDescriptions(tool=tool, capabilities=caps)


def _build_prompt(dataset_name: str, tables: list[dict]) -> str:
    """Build the catalog-assistant prompt describing the dataset and every table."""
    lines = [
        _DESCRIBE_TAG,
        "You are a data catalog assistant. Analyze the dataset below and write concise, accurate",
        "metadata for a tool registry: one description for the whole dataset, and one per table.",
        "",
        f"Dataset name: {dataset_name}",
        "",
        "Tables:",
    ]
    for t in tables:
        schema = t.get("schema") or []
        cols = ", ".join(
            f"{c['name']} ({c['dtype']}{'?' if c.get('nullable') else ''})" for c in schema
        ) or "(unknown)"
        lines.append(f"Table: {t['table_name']}  (rows: {t.get('row_count', 0)})")
        lines.append(f"  columns: {cols}")
        sample = _sample(t.get("parquet_path"))
        if sample:
            lines.append("  sample (first rows):")
            lines.append(sample)
    lines += [
        "",
        "Respond with ONLY a JSON object, no prose, no markdown fences:",
        '{"tool_description": "<1-2 sentences about the whole dataset>",',
        ' "capabilities": {"<table_name>": "<1 sentence about querying that table>"}}',
    ]
    return "\n".join(lines)


def _sample(parquet_path: str | None) -> str:
    """Return a small CSV sample of a Parquet file, or empty string on any failure."""
    if not parquet_path:
        return ""
    try:
        return pd.read_parquet(parquet_path).head(5).to_csv(index=False)
    except Exception:
        return ""


def _parse(raw: str, fallback: DatasetDescriptions) -> DatasetDescriptions:
    """Parse the model's JSON reply (tolerating fences); fall back per field/table."""
    parsed = json.loads(_strip_markdown_fences(raw.strip()))
    tool = parsed.get("tool_description") or fallback.tool
    caps_in = parsed.get("capabilities") or {}
    # fallback.capabilities holds the authoritative table list; fill any missing table from it.
    caps = {name: (caps_in.get(name) or default) for name, default in fallback.capabilities.items()}
    return DatasetDescriptions(tool=tool, capabilities=caps)


def _strip_markdown_fences(text: str) -> str:
    """Remove a leading ``` fence (and optional language tag) some models emit."""
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
    return "\n".join(lines[1:end]).strip()
