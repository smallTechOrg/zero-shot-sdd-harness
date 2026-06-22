from __future__ import annotations
import re

_UNSAFE = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|MERGE|CALL|EXEC|EXECUTE)\b",
    re.IGNORECASE | re.MULTILINE,
)


def extract_sql(raw_response: str) -> str:
    """Strip markdown fences, validate SELECT-only. Raises ValueError on violation."""
    text = raw_response.strip()

    # Strip ```sql ... ``` or ``` ... ``` fences
    fence_match = re.search(r"```(?:sql)?\s*([\s\S]+?)\s*```", text, re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    # Must start with SELECT (after stripping whitespace / WITH clause)
    stripped = text.lstrip()
    if not re.match(r"^\s*(WITH\b|SELECT\b)", stripped, re.IGNORECASE):
        raise ValueError(f"Response does not contain a SELECT statement: {text[:200]}")

    # Reject unsafe keywords
    if _UNSAFE.search(text):
        raise ValueError(f"Unsafe SQL detected: {text[:200]}")

    # Reject multi-statement SQL (e.g., SELECT 1; DROP TABLE t)
    if ";" in text:
        raise ValueError("Multi-statement SQL is not permitted")

    return text
