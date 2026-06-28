"""In-memory DataFrame cache + file-store loader.

The loaded DataFrame lives here, keyed by ``dataset_id`` — it is NEVER written
to the database and NEVER serialised into an LLM payload. The agent's
``node_execute`` reads the frame from this store (not from graph state) so raw
rows stay server-side.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pandas as pd

from config.settings import get_settings


class DatasetStore:
    """Process-wide cache of loaded DataFrames + a managed file loader."""

    def __init__(self, store_dir: str | None = None) -> None:
        self._frames: dict[str, pd.DataFrame] = {}
        self._lock = threading.RLock()
        self._store_dir = Path(store_dir) if store_dir else Path(get_settings().dataset_store_dir)

    @property
    def store_dir(self) -> Path:
        return self._store_dir

    def put(self, dataset_id: str, df: pd.DataFrame) -> None:
        with self._lock:
            self._frames[dataset_id] = df

    def get(self, dataset_id: str) -> pd.DataFrame | None:
        with self._lock:
            return self._frames.get(dataset_id)

    def has(self, dataset_id: str) -> bool:
        with self._lock:
            return dataset_id in self._frames

    def evict(self, dataset_id: str) -> None:
        with self._lock:
            self._frames.pop(dataset_id, None)

    def load(self, dataset_id: str, file_path: str | None = None) -> pd.DataFrame:
        """Return the cached frame, loading from ``file_path`` on a miss.

        Reads CSV or Excel based on the file extension. The result is cached
        under ``dataset_id`` for subsequent runs.
        """
        with self._lock:
            cached = self._frames.get(dataset_id)
            if cached is not None:
                return cached
        if file_path is None:
            raise KeyError(
                f"dataset {dataset_id!r} not cached and no file_path provided to load it"
            )
        df = read_file(file_path)
        self.put(dataset_id, df)
        return df


def read_file(file_path: str | Path) -> pd.DataFrame:
    """Load a CSV or Excel file into a DataFrame."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in (".csv", ".txt"):
        return pd.read_csv(path)
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)
    raise ValueError(f"unsupported file type: {suffix!r} (expected .csv or .xlsx)")


# Process-wide singleton — the API and the graph runner share one store.
_store: DatasetStore | None = None


def get_dataset_store() -> DatasetStore:
    global _store
    if _store is None:
        _store = DatasetStore()
    return _store
