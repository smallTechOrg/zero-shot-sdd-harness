"""Deterministic chart-type heuristic + the aggregate-cap helper. No LLM.

``pick_chart`` maps an aggregate result shape to ONE chart spec. ``to_aggregate``
bounds a full local result to ``AGG_ROW_CAP`` rows — the privacy cap the graph's
``privacy_guard`` enforces before any result data reaches the LLM.
"""
from __future__ import annotations

# The privacy/aggregate cap: at most this many rows of result data ever go to
# the LLM (the guard calls ``to_aggregate`` to enforce it).
AGG_ROW_CAP = 50

# Heuristic: a part-of-whole pie only makes sense for a small number of slices.
_MAX_PIE_SLICES = 6

# Column-name hints that suggest an ordered / time dimension → line chart.
_TIME_HINTS = (
    "date",
    "month",
    "year",
    "day",
    "week",
    "quarter",
    "time",
    "period",
    "ts",
    "timestamp",
)

# Column-name hints that suggest a part-of-whole measure → pie chart.
_SHARE_HINTS = ("share", "percent", "pct", "proportion", "ratio")


def _looks_numeric(values: list) -> bool:
    """True if every non-null value in the column is a number (int/float)."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return False
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null)


def _is_time_like(name: str) -> bool:
    low = name.lower()
    return any(h in low for h in _TIME_HINTS)


def _is_share_like(name: str) -> bool:
    low = name.lower()
    return any(h in low for h in _SHARE_HINTS)


def pick_chart(aggregate: dict) -> dict:
    """Pick ONE chart spec deterministically from an aggregate result shape.

    Rules (in order):
      - exactly one dimension (1st column) + exactly one numeric measure (2nd):
          * dimension name looks time/ordered  → ``line``
          * measure name looks part-of-whole AND few slices → ``pie``
          * otherwise (categorical dimension)   → ``bar``
      - anything else (scalar, multi-measure, no numeric measure, empty) → ``table``

    Returns ``{"type": "bar"|"line"|"pie", "x": <dim>, "y": <measure>}`` or
    ``{"type": "table"}``.
    """
    columns = aggregate.get("columns") or []
    rows = aggregate.get("rows") or []

    # Need exactly two columns: one dimension + one measure.
    if len(columns) != 2 or not rows:
        return {"type": "table"}

    dim_name, measure_name = columns[0], columns[1]
    measure_values = [r[1] for r in rows]
    dim_values = [r[0] for r in rows]

    # The measure must be numeric; the dimension must NOT be (it's a category/axis).
    if not _looks_numeric(measure_values):
        return {"type": "table"}
    if _looks_numeric(dim_values):
        return {"type": "table"}

    if _is_time_like(dim_name):
        return {"type": "line", "x": dim_name, "y": measure_name}

    if _is_share_like(measure_name) and len(rows) <= _MAX_PIE_SLICES:
        return {"type": "pie", "x": dim_name, "y": measure_name}

    return {"type": "bar", "x": dim_name, "y": measure_name}


def to_aggregate(result: dict, cap: int = AGG_ROW_CAP) -> dict:
    """Bound a full local result to at most ``cap`` rows for the LLM.

    Returns ``{"columns", "rows" (≤ cap), "total_rows", "truncated"}``. The
    privacy_guard uses this so no full-table dump ever reaches the LLM.
    """
    columns = result.get("columns") or []
    rows = result.get("rows") or []
    total = len(rows)
    capped = rows[:cap]
    return {
        "columns": list(columns),
        "rows": [list(r) for r in capped],
        "total_rows": total,
        "truncated": total > cap,
    }
