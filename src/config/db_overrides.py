"""Runtime DB overrides — reads user-configured settings without going through api/."""
from __future__ import annotations

from db.models import SettingRow
from db.session import create_db_session


def get_runtime_model() -> str | None:
    try:
        with create_db_session() as session:
            row = session.get(SettingRow, "llm_model")
            val = row.value if row is not None else None
        return val.strip() if val and val.strip() else None
    except Exception:
        return None


def get_runtime_max_iterations() -> int | None:
    try:
        with create_db_session() as session:
            row = session.get(SettingRow, "max_iterations")
            val = row.value if row is not None else None
        if not val:
            return None
        n = int(val.strip())
        return n if n > 0 else None
    except Exception:
        return None
