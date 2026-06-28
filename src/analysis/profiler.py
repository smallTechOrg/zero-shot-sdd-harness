"""Dataset profiler — schema, dtypes, ranges, quality flags.

PRIVACY: the returned profile contains ONLY schema-level facts and computed
aggregates (counts, min/max). It NEVER contains raw cell values from the data
body. This profile is one of the few things allowed past the privacy gate.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def profile(df: pd.DataFrame) -> dict[str, Any]:
    """Return a privacy-safe profile of ``df``.

    Shape::

        {
          "row_count": int,
          "col_count": int,
          "columns": [{"name", "dtype", "n_unique", "n_null"}, ...],
          "ranges": {col: {"min": ..., "max": ...}},   # numeric/datetime only
          "quality_flags": [str, ...],
        }
    """
    columns: list[dict[str, Any]] = []
    ranges: dict[str, dict[str, Any]] = {}
    quality_flags: list[str] = []

    n_rows = int(len(df))

    for name in df.columns:
        col = df[name]
        dtype = str(col.dtype)
        n_null = int(col.isna().sum())
        try:
            n_unique = int(col.nunique(dropna=True))
        except TypeError:
            # Unhashable values (e.g. lists) — fall back to a safe estimate.
            n_unique = int(col.astype(str).nunique(dropna=True))

        columns.append(
            {
                "name": str(name),
                "dtype": dtype,
                "n_unique": n_unique,
                "n_null": n_null,
            }
        )

        # Ranges only for numeric / datetime — these are aggregates, not raw rows.
        if pd.api.types.is_numeric_dtype(col) or pd.api.types.is_datetime64_any_dtype(col):
            non_null = col.dropna()
            if not non_null.empty:
                ranges[str(name)] = {
                    "min": _scalar(non_null.min()),
                    "max": _scalar(non_null.max()),
                }

        # Quality flags ----------------------------------------------------
        if n_rows and n_null / n_rows > 0.5:
            quality_flags.append(f"column '{name}' is more than 50% null")

        if _looks_like_unparsed_dates(col, name):
            quality_flags.append(
                f"column '{name}' looks like dates but is stored as text"
            )

        if _is_mixed_type(col):
            quality_flags.append(f"column '{name}' has mixed value types")

    dup_count = int(df.duplicated().sum())
    if dup_count:
        quality_flags.append(f"{dup_count} fully-duplicate rows")

    return {
        "row_count": n_rows,
        "col_count": int(df.shape[1]),
        "columns": columns,
        "ranges": ranges,
        "quality_flags": quality_flags,
    }


def _scalar(value: Any) -> Any:
    """Coerce a numpy/pandas scalar into a JSON-safe Python value."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _looks_like_unparsed_dates(col: pd.Series, name: str) -> bool:
    if not (pd.api.types.is_object_dtype(col) or pd.api.types.is_string_dtype(col)):
        return False
    lname = str(name).lower()
    if not any(tok in lname for tok in ("date", "time", "day", "month", "year")):
        return False
    sample = col.dropna().astype(str).head(50)
    if sample.empty:
        return False
    try:
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(sample, errors="coerce")
    except (ValueError, TypeError):
        return False
    return parsed.notna().mean() > 0.8


def _is_mixed_type(col: pd.Series) -> bool:
    if not pd.api.types.is_object_dtype(col):
        return False
    non_null = col.dropna()
    if non_null.empty:
        return False
    types = non_null.map(type).nunique()
    return types > 1
