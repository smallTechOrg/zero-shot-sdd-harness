import json
import re

from sqlalchemy import text

from db.session import create_db_session
from db.models import DatasetRow


def _sanitize_name(filename: str) -> str:
    """filename without extension → valid SQLite table name component."""
    name = re.sub(r"\.[^.]+$", "", filename)  # remove extension
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    if not name or name[0].isdigit():
        name = "t_" + name
    return name[:50]  # cap length


def _session_prefix(session_id: str) -> str:
    return session_id.replace("-", "_")


def load_dataset(session_id: str, filename: str, df) -> dict:
    """
    Ingest DataFrame into SQLite dynamic table, write DatasetRow.

    Returns a plain dict with all DatasetRow fields (detachment-safe).
    """
    from datetime import datetime, timezone
    from db.session import _get_engine

    sanitized = _sanitize_name(filename)
    prefix = _session_prefix(session_id)
    table_name = f"{prefix}_{sanitized}"
    engine = _get_engine()

    # Use a single connection for drop + create so we never hold two write locks
    with engine.connect() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
        conn.commit()
        df.to_sql(table_name, conn, index=False, if_exists="replace")
        conn.commit()

    row_count = len(df)
    column_names = json.dumps(list(df.columns))
    now = datetime.now(timezone.utc)

    with create_db_session() as session:
        # Delete old DatasetRow for this table if any
        old = session.query(DatasetRow).filter_by(table_name=table_name).first()
        if old:
            session.delete(old)
            session.flush()

        row = DatasetRow(
            session_id=session_id,
            table_name=table_name,
            original_filename=filename,
            row_count=row_count,
            column_names=column_names,
        )
        session.add(row)
        session.flush()
        # Capture all fields before session closes (avoid DetachedInstanceError)
        result = {
            "id": row.id,
            "session_id": row.session_id,
            "table_name": row.table_name,
            "original_filename": row.original_filename,
            "row_count": row.row_count,
            "column_names": row.column_names,
            "created_at": row.created_at if row.created_at is not None else now,
        }

    return result
