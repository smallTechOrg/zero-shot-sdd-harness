from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    from data_analyst.db.models import DatasetRow

# Module-level singleton connection (thread-safe for reads)
_conn: duckdb.DuckDBPyConnection | None = None


def _get_conn() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        _conn = duckdb.connect()
    return _conn


def drop_connection() -> None:
    """For test teardown only."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


def _safe_table_name(name: str) -> str:
    """Convert filename to a safe SQL identifier."""
    stem = Path(name).stem
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", stem)
    if safe and safe[0].isdigit():
        safe = "t_" + safe
    if not safe:
        safe = "table_data"
    return safe


def register_dataset(
    session_id: str,
    table_name: str,
    file_path: str,
    file_format: str,
) -> int:
    """Register a file as a DuckDB view. Returns row count."""
    conn = _get_conn()
    fp = str(Path(file_path).resolve())
    fp_safe = fp.replace("'", "''")

    if file_format == "csv":
        conn.execute(
            f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_csv_auto('{fp_safe}')"
        )
    elif file_format == "json":
        conn.execute(
            f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_json_auto('{fp_safe}')"
        )
    elif file_format == "parquet":
        conn.execute(
            f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{fp_safe}')"
        )
    else:
        raise ValueError(f"Unsupported file format: {file_format}")

    result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    return result[0] if result else 0


def execute_query(sql: str) -> list[dict]:
    """Execute a SQL query and return results as list of dicts."""
    conn = _get_conn()
    rel = conn.execute(sql)
    columns = [desc[0] for desc in rel.description]
    rows = rel.fetchall()
    return [dict(zip(columns, row)) for row in rows]


def get_table_schema(table_name: str) -> list[dict]:
    """Return column info for a registered view/table."""
    conn = _get_conn()
    result = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return [{"name": row[1], "type": row[2]} for row in result]


def reregister_session_datasets(datasets: list) -> None:
    """Re-register all datasets for a session after process restart."""
    for ds in datasets:
        try:
            register_dataset(
                session_id=ds.session_id,
                table_name=ds.table_name,
                file_path=ds.file_path,
                file_format=ds.file_format,
            )
        except Exception as exc:
            import sys
            print(f"Warning: could not re-register {ds.table_name}: {exc}", file=sys.stderr)
