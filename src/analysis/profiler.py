"""Profile a DataFrame into the JSON-serializable shape stored on a Dataset.

Output shape (see spec/data.md, spec/api.md)::

    {
      "columns": [
        {"name": str, "dtype": str, "null_count": int, "sample_values": [...]}
      ],
      "quality_flags": [str, ...],
      "sample_rows": [{col: value, ...}, ...],
    }

Everything returned is JSON-serializable (numpy scalars coerced, NaN -> None).
"""
from __future__ import annotations

import pandas as pd
from pandas.api import types as ptypes

from analysis._serialize import to_json_safe


def _friendly_dtype(series: pd.Series) -> str:
    """Map a pandas column dtype to a friendly string."""
    if ptypes.is_bool_dtype(series):
        return "bool"
    if ptypes.is_integer_dtype(series):
        return "int64"
    if ptypes.is_float_dtype(series):
        return "float64"
    if ptypes.is_datetime64_any_dtype(series):
        return "datetime64"
    if ptypes.is_numeric_dtype(series):
        # Remaining numerics (e.g. complex) — report the raw name.
        return str(series.dtype)
    # object, string, category, and everything text-like.
    return "string"


def _sample_values(series: pd.Series, limit: int = 3) -> list:
    """Up to ``limit`` distinct non-null example values, JSON-safe."""
    non_null = series.dropna()
    if non_null.empty:
        return []
    seen: list = []
    out: list = []
    for raw in non_null.tolist():
        safe = to_json_safe(raw)
        # De-duplicate on the JSON-safe representation.
        key = safe if isinstance(safe, (str, int, float, bool, type(None))) else str(safe)
        if key in seen:
            continue
        seen.append(key)
        out.append(safe)
        if len(out) >= limit:
            break
    return out


def profile(df: pd.DataFrame, sample_n: int = 5) -> dict:
    """Profile ``df`` into the canonical JSON-serializable profile dict."""
    row_count = int(df.shape[0])

    columns: list[dict] = []
    quality_flags: list[str] = []

    for name in df.columns:
        series = df[name]
        null_count = int(series.isna().sum())
        columns.append(
            {
                "name": str(name),
                "dtype": _friendly_dtype(series),
                "null_count": null_count,
                "sample_values": _sample_values(series),
            }
        )

        # Null flag.
        if null_count > 0 and row_count > 0:
            pct = null_count / row_count * 100
            quality_flags.append(
                f"column '{name}' has {null_count} nulls ({pct:.2f}%)"
            )

        # Constant-column flag (single distinct non-null value across all rows).
        non_null = series.dropna()
        if row_count > 0 and not non_null.empty and non_null.nunique(dropna=True) == 1:
            quality_flags.append(f"column '{name}' is constant")

    # Fully-duplicated rows.
    if row_count > 0:
        dup_count = int(df.duplicated(keep="first").sum())
        if dup_count > 0:
            quality_flags.append(f"{dup_count} duplicate rows")

    # Sample rows (first ``sample_n``), JSON-safe with NaN -> None.
    head = df.head(max(0, int(sample_n)))
    sample_rows = [to_json_safe(record) for record in head.to_dict(orient="records")]

    return {
        "columns": columns,
        "quality_flags": quality_flags,
        "sample_rows": sample_rows,
    }
