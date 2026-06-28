"""Schema + sample-row extraction for an uploaded CSV.

Reads ONLY metadata (column names/types), bounded sample rows, and row/column
counts via DuckDB's streaming ``read_csv_auto`` — the full file is never loaded
into Python memory. This is the only place that touches raw rows, and it emits at
most ``sample_rows`` of them (the privacy-bounded slice sent to the LLM).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import duckdb


class LoaderError(Exception):
    """Raised when a file cannot be parsed as a CSV."""


@dataclass
class DatasetProfile:
    row_count: int
    column_count: int
    schema: list[dict]              # [{name, type}, ...]
    sample_rows: list[dict] = field(default_factory=list)


def _duckdb_to_friendly(type_name: str) -> str:
    t = (type_name or "").upper()
    if any(k in t for k in ("INT", "HUGEINT")):
        return "integer"
    if any(k in t for k in ("DOUBLE", "FLOAT", "DECIMAL", "REAL", "NUMERIC")):
        return "number"
    if "BOOL" in t:
        return "boolean"
    if any(k in t for k in ("DATE", "TIME")):
        return "datetime"
    return "string"


def _quote_path(csv_path: str) -> str:
    return csv_path.replace("'", "''")


def load_dataset_metadata(csv_path: str, sample_rows: int = 10) -> DatasetProfile:
    """Extract schema + ≤ ``sample_rows`` sample rows + counts from a CSV.

    Uses DuckDB ``read_csv_auto`` so a 100MB file is streamed, not loaded whole.
    """
    safe = _quote_path(csv_path)
    con = duckdb.connect(database=":memory:")
    try:
        # Column schema (name + inferred type) without reading all rows.
        describe = con.execute(
            f"DESCRIBE SELECT * FROM read_csv_auto('{safe}')"
        ).fetchall()
        schema = [
            {"name": row[0], "type": _duckdb_to_friendly(row[1])}
            for row in describe
        ]

        # Row count over the full file (streamed aggregate, no full load).
        row_count = con.execute(
            f"SELECT COUNT(*) FROM read_csv_auto('{safe}')"
        ).fetchone()[0]

        # Bounded sample rows — the only raw rows that ever leave the engine.
        n = max(0, int(sample_rows))
        sample_cur = con.execute(
            f"SELECT * FROM read_csv_auto('{safe}') LIMIT {n}"
        )
        columns = [d[0] for d in sample_cur.description]
        sample = [
            {col: _jsonify(val) for col, val in zip(columns, rec)}
            for rec in sample_cur.fetchall()
        ]
    except duckdb.Error as exc:
        raise LoaderError(str(exc)) from exc
    finally:
        con.close()

    return DatasetProfile(
        row_count=int(row_count),
        column_count=len(schema),
        schema=schema,
        sample_rows=sample,
    )


def _jsonify(val):
    """Coerce a DuckDB scalar into a JSON-serialisable value."""
    if val is None or isinstance(val, (str, int, float, bool)):
        return val
    return str(val)
