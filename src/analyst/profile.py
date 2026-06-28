"""Lightweight CSV profiling (Phase 1).

Computes only what the privacy-safe prompt needs: row_count, schema
([{name, dtype}]) and a small sample (<= 20 rows). The FULL auto-profile
(ranges / distinct / missing counts) is a Phase 2 concern and is intentionally
NOT computed here.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

MAX_SAMPLE_ROWS = 20


@dataclass
class CsvProfile:
    row_count: int
    schema: list[dict]          # [{name, dtype}]
    sample_rows: list[dict]     # <= 20 rows as JSON-safe records


def _json_safe_records(df: pd.DataFrame) -> list[dict]:
    """Coerce a DataFrame to JSON-safe records (NaN -> None, native types)."""
    safe = df.astype(object).where(pd.notnull(df), None)
    records: list[dict] = []
    for row in safe.to_dict(orient="records"):
        records.append({k: _coerce(v) for k, v in row.items()})
    return records


def _coerce(value):
    if value is None:
        return None
    # numpy scalars -> python scalars
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            return str(value)
    if isinstance(value, (int, float, bool, str)):
        return value
    return str(value)


def profile_csv(path: str) -> CsvProfile:
    """Read the CSV once and derive the minimal, LLM-safe profile.

    Raises ValueError if the file is empty or unparseable by pandas.
    """
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError as exc:
        raise ValueError("CSV file is empty or has no columns") from exc
    except Exception as exc:  # malformed CSV
        raise ValueError(f"Could not parse CSV: {exc}") from exc

    if df.shape[1] == 0:
        raise ValueError("CSV file has no columns")

    schema = [{"name": str(c), "dtype": str(df[c].dtype)} for c in df.columns]
    sample = _json_safe_records(df.head(MAX_SAMPLE_ROWS))
    return CsvProfile(row_count=int(len(df)), schema=schema, sample_rows=sample)
