from sqlalchemy import text

from db.session import _get_engine


def schema_summary(table_name: str) -> list[dict]:
    """Return [{"name": str, "type": str}] for the data table (compact, no rows)."""
    engine = _get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(f'PRAGMA table_info("{table_name}")')
        ).fetchall()
    return [{"name": r[1], "type": (r[2] or "TEXT").upper()} for r in rows]


def sample_rows(table_name: str, n: int = 5) -> dict:
    """Return {"columns": [...], "rows": [[...], ...]} with at most n rows."""
    engine = _get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text(f'SELECT * FROM "{table_name}" LIMIT :n'), {"n": n}
        )
        columns = list(result.keys())
        rows = [list(r) for r in result.fetchall()]
    return {"columns": columns, "rows": rows}
