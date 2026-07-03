"""Build a Vega-Lite v5 spec from the LLM's chart selection + aggregated table.

The LLM emits a *chart selection*::

    {"mark": "bar"|"line"|"point"|"area", "x": "<col>", "y": "<col>", "title": "..."}

``build_vega_spec`` validates that against the aggregated ``table`` (a small
list of dict rows) and embeds the table as ``data.values``. It NEVER raises: an
invalid/missing selection falls back to a sensible default so the run still
returns a renderable chart. Only the aggregated table is embedded — never raw
rows.
"""
from __future__ import annotations

from analysis._serialize import to_json_safe

VEGA_LITE_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"

_VALID_MARKS = {"bar", "line", "point", "area", "tick", "circle"}
_DEFAULT_MARK = "bar"


def _columns(table: list[dict]) -> list[str]:
    """Ordered union of keys across the table rows."""
    cols: list[str] = []
    for row in table:
        if isinstance(row, dict):
            for k in row.keys():
                if k not in cols:
                    cols.append(k)
    return cols


def _is_numeric(table: list[dict], col: str) -> bool:
    for row in table:
        if isinstance(row, dict) and col in row and row[col] is not None:
            return isinstance(row[col], (int, float)) and not isinstance(row[col], bool)
    return False


def _field_type(table: list[dict], col: str) -> str:
    return "quantitative" if _is_numeric(table, col) else "nominal"


def _encoding(table: list[dict], x: str, y: str) -> dict:
    return {
        "x": {"field": x, "type": _field_type(table, x)},
        "y": {"field": y, "type": _field_type(table, y)},
    }


def _default_axes(cols: list[str], table: list[dict]) -> tuple[str, str]:
    """Pick (x=first categorical, y=first numeric); degrade gracefully."""
    numeric = [c for c in cols if _is_numeric(table, c)]
    categorical = [c for c in cols if c not in numeric]
    x = categorical[0] if categorical else (cols[0] if cols else "label")
    if numeric:
        y = numeric[0]
    else:
        y = next((c for c in cols if c != x), x)
    return x, y


def _fallback_spec(table: list[dict], title: str | None = None) -> dict:
    """A renderable default chart for any table (or a placeholder if empty)."""
    safe_table = to_json_safe(table) if isinstance(table, list) else []
    cols = _columns(safe_table) if isinstance(safe_table, list) else []

    if not safe_table or not cols:
        # No usable data — a labelled empty bar so the frontend still renders.
        return {
            "$schema": VEGA_LITE_SCHEMA,
            "title": title or "No chartable data",
            "mark": _DEFAULT_MARK,
            "data": {"values": safe_table or []},
            "encoding": {},
        }

    x, y = _default_axes(cols, safe_table)
    spec = {
        "$schema": VEGA_LITE_SCHEMA,
        "mark": _DEFAULT_MARK,
        "data": {"values": safe_table},
        "encoding": _encoding(safe_table, x, y),
    }
    if title:
        spec["title"] = title
    return spec


def build_vega_spec(selection: dict, table: list[dict]) -> dict:
    """Turn the LLM's chart ``selection`` + aggregated ``table`` into a
    Vega-Lite v5 spec. Falls back to a sensible default when the selection is
    missing or references unknown columns. Never raises."""
    safe_table = to_json_safe(table) if isinstance(table, list) else []
    if not isinstance(safe_table, list):
        safe_table = []

    title = None
    if isinstance(selection, dict):
        raw_title = selection.get("title")
        if isinstance(raw_title, str) and raw_title.strip():
            title = raw_title.strip()

    if not isinstance(selection, dict):
        return _fallback_spec(safe_table, title)

    cols = _columns(safe_table)
    mark = selection.get("mark")
    if not isinstance(mark, str) or mark not in _VALID_MARKS:
        mark = _DEFAULT_MARK

    x = selection.get("x")
    y = selection.get("y")

    # If either axis is missing or not a real column, fall back (keeping title).
    if not (isinstance(x, str) and isinstance(y, str) and x in cols and y in cols):
        spec = _fallback_spec(safe_table, title)
        spec["mark"] = mark
        return spec

    spec = {
        "$schema": VEGA_LITE_SCHEMA,
        "mark": mark,
        "data": {"values": safe_table},
        "encoding": _encoding(safe_table, x, y),
    }
    if title:
        spec["title"] = title
    return spec
