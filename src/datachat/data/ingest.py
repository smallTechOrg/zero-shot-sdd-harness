"""CSV ingestion — parse with pandas, infer schema, materialize into DuckDB.

Only the inferred schema + a small row sample are ever surfaced to the LLM; the full
dataset stays in DuckDB and is queried there (never sent to the model).
"""

from __future__ import annotations

import io
import re
import uuid

import pandas as pd

from datachat.config.settings import get_settings
from datachat.data import engine

_SAFE_NAME = re.compile(r"[^a-z0-9_]+")


def _table_name(dataset_id: str, filename: str) -> str:
    stem = filename.rsplit(".", 1)[0].lower()
    stem = _SAFE_NAME.sub("_", stem).strip("_") or "file"
    suffix = uuid.uuid4().hex[:8]
    short_ds = dataset_id.replace("-", "")[:8]
    return f"ds_{short_ds}_{stem}_{suffix}"


class IngestResult:
    def __init__(
        self,
        duckdb_table: str,
        schema_columns: list[dict],
        sample_rows: list[list],
        row_count: int,
    ) -> None:
        self.duckdb_table = duckdb_table
        self.schema_columns = schema_columns
        self.sample_rows = sample_rows
        self.row_count = row_count


def ingest_csv(dataset_id: str, filename: str, raw: bytes) -> IngestResult:
    """Load a CSV into the dataset's DuckDB engine; return schema + sample for grounding.

    Raises ValueError on an empty/unparseable CSV so the API can return a clean error.
    """
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:  # pandas raises many parse error types
        raise ValueError(f"Could not parse CSV '{filename}': {exc}") from exc

    if df.shape[1] == 0:
        raise ValueError(f"CSV '{filename}' has no columns.")

    table = _table_name(dataset_id, filename)
    conn = engine.get_connection(dataset_id)
    conn.register("_ingest_df", df)
    conn.execute(f'CREATE TABLE "{table}" AS SELECT * FROM _ingest_df')
    conn.unregister("_ingest_df")

    schema_columns = [
        {"name": str(name), "type": str(dtype)}
        for name, dtype in zip(df.columns, df.dtypes, strict=True)
    ]

    sample_n = get_settings().sample_rows
    sample_df = df.head(sample_n)
    sample_rows = sample_df.astype(object).where(pd.notnull(sample_df), None).values.tolist()

    return IngestResult(
        duckdb_table=table,
        schema_columns=schema_columns,
        sample_rows=sample_rows,
        row_count=int(df.shape[0]),
    )


def rematerialize(dataset_id: str, table: str, raw: bytes) -> None:
    """Recreate a DuckDB table from stored CSV bytes (after a process restart)."""
    df = pd.read_csv(io.BytesIO(raw))
    conn = engine.get_connection(dataset_id)
    conn.register("_ingest_df", df)
    conn.execute(f'CREATE OR REPLACE TABLE "{table}" AS SELECT * FROM _ingest_df')
    conn.unregister("_ingest_df")
