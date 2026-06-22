"""Owns the single shared DuckDB connection. Read-only query execution."""
import re
import threading
from pathlib import Path

import duckdb

_DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "analytics.duckdb"

_lock = threading.Lock()
_conn: "duckdb.DuckDBPyConnection | None" = None
_conn_path: str | None = None

# Reject anything that is not a single read-only SELECT/WITH statement.
_SELECT_RE = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


class NonSelectError(ValueError):
    """Raised when a statement is not a single read-only SELECT."""


def _db_path() -> str:
    from config.settings import get_settings

    override = getattr(get_settings(), "duckdb_path", "") or ""
    return override or str(_DEFAULT_PATH)


def get_connection() -> "duckdb.DuckDBPyConnection":
    """Return the process-wide shared DuckDB connection (created on first use)."""
    global _conn, _conn_path
    path = _db_path()
    with _lock:
        if _conn is None or _conn_path != path:
            if _conn is not None:
                _conn.close()
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            _conn = duckdb.connect(path)
            _conn_path = path
        return _conn


def reset_connection() -> None:
    """Drop the cached connection (test isolation)."""
    global _conn, _conn_path
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        _conn_path = None


def _assert_select(sql: str) -> None:
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise NonSelectError("Empty SQL statement.")
    if ";" in stripped:
        raise NonSelectError("Multiple statements are not allowed; only a single SELECT.")
    if not _SELECT_RE.match(stripped):
        raise NonSelectError("Only read-only SELECT statements are permitted.")


class DuckDBStore:
    """Thin facade over the shared DuckDB connection."""

    def execute_select(self, sql: str) -> tuple[list[str], list[list]]:
        """Run a read-only SELECT. Returns (columns, rows). Rejects non-SELECT."""
        _assert_select(sql)
        conn = get_connection()
        with _lock:
            cur = conn.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = [list(r) for r in cur.fetchall()]
        return columns, rows

    def table_exists(self, table: str) -> bool:
        conn = get_connection()
        with _lock:
            res = conn.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
                [table],
            ).fetchone()
        return res is not None
