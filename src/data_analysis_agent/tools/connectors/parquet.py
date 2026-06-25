"""Internal Parquet dataset connector: a directory of Parquet files, one view (table) per file."""
from __future__ import annotations

from pathlib import Path

import duckdb

from data_analysis_agent.tools.connectors.base import DatasetConnectionError
from data_analysis_agent.tools.mcp.server import (
    DEFAULT_MAX_ROWS,
    build_server,
    new_connection,
    register_parquet_view,
)


class ParquetConnector:
    """Serves a `parquet` dataset. ``tables`` are dicts with ``table_name`` + ``parquet_path``."""

    def __init__(self, server: dict, tables: list[dict]) -> None:
        self._server = server
        self._tables = list(tables)

    def connection_check(self) -> None:
        """Verify every table's Parquet file exists and is readable; raise on failure."""
        for table in self._tables:
            path = table.get("parquet_path")
            name = table.get("table_name")
            if not path or not Path(path).exists():
                raise DatasetConnectionError(f"Dataset file is missing for table '{name}'.")
            try:
                conn = duckdb.connect(database=":memory:")
                safe = path.replace("'", "''")
                conn.execute(f"SELECT * FROM read_parquet('{safe}') LIMIT 0")
                conn.close()
            except duckdb.Error as exc:
                raise DatasetConnectionError(f"Dataset file unreadable for table '{name}': {exc}")

    def discover_tables(self) -> list[dict]:
        """Parquet tables are known at upload time; echo the provided table dicts."""
        return list(self._tables)

    def build_server(self, max_rows: int = DEFAULT_MAX_ROWS):
        """Open one DuckDB connection with a view per Parquet file and build the MCP server."""
        conn = new_connection()
        for table in self._tables:
            register_parquet_view(conn, table["table_name"], table.get("parquet_path"))
        return build_server(self._server.get("name") or "dataset", conn, self._tables, max_rows)
