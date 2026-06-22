"""CSV → pandas → DuckDB ingest. Captures column schema (name, duckdb type)."""
from __future__ import annotations

import io

import pandas as pd

from analytics.duckdb_store import get_connection, _lock


class IngestError(ValueError):
    """Raised when an uploaded file cannot be parsed/ingested."""


def _quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def ingest_csv(*, content: bytes, table: str) -> tuple[int, list[dict]]:
    """Parse CSV bytes into a DuckDB table.

    Returns (row_count, schema) where schema is [{name, type}] using DuckDB types.
    Raises IngestError on empty/unparseable input.
    """
    if not content or not content.strip():
        raise IngestError("Uploaded file is empty.")

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:  # pandas raises a wide variety of parse errors
        raise IngestError(f"Could not parse CSV: {exc}") from exc

    if df.shape[1] == 0:
        raise IngestError("CSV has no columns.")
    if df.shape[0] == 0:
        raise IngestError("CSV has no data rows.")

    conn = get_connection()
    with _lock:
        conn.register("_ingest_df", df)
        try:
            conn.execute(f"DROP TABLE IF EXISTS {_quote_ident(table)}")
            conn.execute(
                f"CREATE TABLE {_quote_ident(table)} AS SELECT * FROM _ingest_df"
            )
        finally:
            conn.unregister("_ingest_df")

        info = conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position",
            [table],
        ).fetchall()
        row_count = conn.execute(
            f"SELECT COUNT(*) FROM {_quote_ident(table)}"
        ).fetchone()[0]

    schema = [{"name": name, "type": dtype} for name, dtype in info]
    return int(row_count), schema
