"""DuckDB analytical engine — session-scoped per dataset (module-level store).

The DuckDB connection holding a dataset's tables is a **session-scoped resource**
(patterns/react-agent.md § Resource lifecycle): kept in a module-level store keyed by
`dataset_id`, shared across runs in the same conversation, and released only when the
dataset is deleted — never in terminal graph nodes.
"""

from __future__ import annotations

import threading

import duckdb

_engines: dict[str, duckdb.DuckDBPyConnection] = {}
_lock = threading.Lock()


def get_connection(dataset_id: str) -> duckdb.DuckDBPyConnection:
    """Return the dataset's in-process DuckDB connection, creating it on first use."""
    with _lock:
        conn = _engines.get(dataset_id)
        if conn is None:
            conn = duckdb.connect(database=":memory:")
            _engines[dataset_id] = conn
        return conn


def has_connection(dataset_id: str) -> bool:
    with _lock:
        return dataset_id in _engines


def release(dataset_id: str) -> None:
    """Drop the dataset's DuckDB connection. Call only on dataset deletion."""
    with _lock:
        conn = _engines.pop(dataset_id, None)
    if conn is not None:
        conn.close()


def list_tables(dataset_id: str) -> list[str]:
    conn = get_connection(dataset_id)
    rows = conn.execute("SHOW TABLES").fetchall()
    return [r[0] for r in rows]
