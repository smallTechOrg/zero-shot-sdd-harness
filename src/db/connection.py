import os

import duckdb

from src.config import settings
from src.db.schema import create_tables


def get_db() -> duckdb.DuckDBPyConnection:
    dirname = os.path.dirname(settings.analyst_db_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    return duckdb.connect(settings.analyst_db_path)


def restore_views(conn: duckdb.DuckDBPyConnection) -> int:
    """Re-create dataset views from the datasets table. Returns count of views restored."""
    from src.datasets.ingest import _build_read_expr  # avoid circular import at module level

    rows = conn.execute("SELECT name, file_path, file_type FROM datasets").fetchall()
    restored = 0
    for name, file_path, file_type in rows:
        try:
            read_expr = _build_read_expr(file_path, file_type)
            conn.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM {read_expr}")
            restored += 1
        except Exception:
            pass  # file may be missing; skip silently
    return restored


def init_db() -> None:
    conn = get_db()
    create_tables(conn)
    conn.close()
