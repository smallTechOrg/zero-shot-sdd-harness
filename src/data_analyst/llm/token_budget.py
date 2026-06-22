from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Rough estimate: 1 token ≈ 4 characters."""
    return max(1, len(text) // 4)


def build_prompt(
    schemas: list[dict],
    history: list[dict],
    question: str,
) -> str:
    """Build a prompt from schema context, history, and the current question."""
    parts = [
        "You are a SQL expert. Given the following table schemas, generate a valid SQLite/DuckDB SQL SELECT query to answer the user's question.",
        "Return ONLY the SQL query, optionally wrapped in ```sql ... ``` fences. Do not include any other text.",
        "",
        "=== TABLE SCHEMAS ===",
    ]
    for schema in schemas:
        table_name = schema["table_name"]
        columns = schema["columns"]
        col_defs = ", ".join(f"{c['name']} ({c['type']})" for c in columns)
        parts.append(f"Table: {table_name} — Columns: {col_defs}")

    if history:
        parts.append("")
        parts.append("=== CONVERSATION HISTORY (most recent last) ===")
        for turn in history:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            parts.append(f"{role.upper()}: {content}")

    parts.append("")
    parts.append(f"USER QUESTION: {question}")
    return "\n".join(parts)


def check_budget(prompt: str, hard_cap: int) -> tuple[bool, int]:
    """Returns (within_budget, estimated_tokens)."""
    estimated = estimate_tokens(prompt)
    return estimated <= hard_cap, estimated
