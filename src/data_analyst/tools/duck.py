import re
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import duckdb

from data_analyst.config.settings import get_settings
from data_analyst.domain import ColumnSchema, ResultTable

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|copy|pragma|export|install|load)\b",
    re.IGNORECASE,
)


def _json_safe(value: Any) -> Any:
    """Coerce DuckDB native values into JSON-serializable forms.

    DuckDB returns date/datetime/Decimal/bytes/UUID objects that SQLAlchemy's
    JSON column cannot serialize. These are persisted (sample rows, result
    tables) so they must be plain JSON types.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return str(value)


class SQLNotReadOnlyError(ValueError):
    """Raised when generated SQL is not a single read-only statement."""


def _connect() -> duckdb.DuckDBPyConnection:
    path = get_settings().duckdb_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(path)


def sanitize_table_name(raw: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z_]", "_", raw).strip("_").lower()
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned


def assert_read_only(sql: str) -> None:
    statements = [s for s in sql.strip().rstrip(";").split(";") if s.strip()]
    if len(statements) != 1:
        raise SQLNotReadOnlyError("Only a single SQL statement is allowed.")
    stmt = statements[0].strip()
    if not re.match(r"^(select|with)\b", stmt, re.IGNORECASE):
        raise SQLNotReadOnlyError("Only SELECT/WITH read-only queries are allowed.")
    if _FORBIDDEN.search(stmt):
        raise SQLNotReadOnlyError("Query contains a forbidden write/DDL keyword.")


def ingest_file(
    file_path: str, table_name: str, file_format: str
) -> tuple[int, list[ColumnSchema]]:
    """Load a CSV/Parquet file into a DuckDB table. Returns (row_count, schema)."""
    table = sanitize_table_name(table_name)
    con = _connect()
    try:
        quoted_path = file_path.replace("'", "''")
        if file_format == "csv":
            reader = f"read_csv_auto('{quoted_path}')"
        elif file_format == "parquet":
            reader = f"read_parquet('{quoted_path}')"
        else:
            raise ValueError(f"Unsupported format: {file_format}")

        con.execute(f'CREATE OR REPLACE TABLE "{table}" AS SELECT * FROM {reader}')
        row_count = con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        described = con.execute(f'DESCRIBE "{table}"').fetchall()
        schema = [ColumnSchema(name=row[0], type=str(row[1])) for row in described]
        return int(row_count), schema
    finally:
        con.close()


def get_sample_rows(table_name: str, limit: int) -> list[dict[str, Any]]:
    table = sanitize_table_name(table_name)
    con = _connect()
    try:
        cursor = con.execute(f'SELECT * FROM "{table}" LIMIT {int(limit)}')
        columns = [d[0] for d in cursor.description]
        return [
            {col: _json_safe(val) for col, val in zip(columns, row)}
            for row in cursor.fetchall()
        ]
    finally:
        con.close()


def run_query(sql: str) -> ResultTable:
    """Execute a validated read-only query and return columns + rows."""
    assert_read_only(sql)
    con = _connect()
    try:
        cursor = con.execute(sql)
        columns = [d[0] for d in cursor.description]
        rows = [[_json_safe(v) for v in r] for r in cursor.fetchall()]
        return ResultTable(columns=columns, rows=rows)
    finally:
        con.close()
