"""In-memory session store: maps session_id -> pd.DataFrame.
DataFrame lives in RAM only; never written to disk."""
from typing import Dict

import pandas as pd

_SESSION_STORE: Dict[str, pd.DataFrame] = {}


def put(session_id: str, df: pd.DataFrame) -> None:
    _SESSION_STORE[session_id] = df


def get(session_id: str) -> pd.DataFrame | None:
    return _SESSION_STORE.get(session_id)


def delete(session_id: str) -> None:
    _SESSION_STORE.pop(session_id, None)
