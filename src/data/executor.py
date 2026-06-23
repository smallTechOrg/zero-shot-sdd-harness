import sqlite3

from db.session import _get_engine


def _sqlite_path() -> str:
    """Resolve the on-disk file path of the configured SQLite engine."""
    url = _get_engine().url
    if url.get_backend_name() != "sqlite":
        raise RuntimeError("run_read_only requires a SQLite database.")
    database = url.database
    if not database or database == ":memory:":
        raise RuntimeError("run_read_only requires a file-based SQLite database.")
    return database


def run_read_only(sql: str) -> dict:
    """Execute SQL on a READ-ONLY SQLite connection (mode=ro + query_only=ON).
    Return {"columns": [...], "rows": [[...], ...]}. Raises on SQL error."""
    path = _sqlite_path()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = [list(r) for r in cursor.fetchall()]
        return {"columns": columns, "rows": rows}
    finally:
        conn.close()
