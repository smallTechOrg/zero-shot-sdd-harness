"""Dataset connector protocol + factory.

The query path must never branch on dataset type inline. ``get_connector`` dispatches on the
dataset's ``type`` to a concrete connector that knows how to validate, introspect, and build the
dataset's MCP server. New engines = one new connector class + one branch here.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from mcp.server.fastmcp import FastMCP


class DatasetConnectionError(Exception):
    """A dataset's URI could not be connected/validated. Messages are ALWAYS credential-free."""


@runtime_checkable
class DatasetConnector(Protocol):
    """How the app validates, introspects, and serves a dataset (parquet, postgres, …)."""

    def connection_check(self) -> None:
        """Validate the dataset is reachable/readable; raise ``DatasetConnectionError`` on failure."""
        ...

    def discover_tables(self) -> list[dict]:
        """Return the dataset's tables: ``[{table_name, column_names, schema, row_count}]``."""
        ...

    def build_server(self, max_rows: int) -> FastMCP:
        """Build the server's in-process MCP server (one generic ``query`` tool over its tables)."""
        ...


def get_connector(server: dict, tables: list[dict]) -> DatasetConnector:
    """Return the connector for a server dict (``type`` + ``uri`` + ``name``) and its table dicts.

    Raises:
        DatasetConnectionError: for an unknown type, or an external type while external datasets
            are disabled (the import of the external connector is lazy so its driver is optional).
    """
    dtype = (server.get("type") or "parquet").lower()
    if dtype == "parquet":
        from data_analysis_agent.tools.connectors.parquet import ParquetConnector
        return ParquetConnector(server, tables)
    if dtype in ("postgresql", "postgres"):
        from data_analysis_agent.config.settings import get_settings
        if not get_settings().enable_external_datasets:
            raise DatasetConnectionError(
                "External database datasets are disabled. Set DATAANALYSIS_ENABLE_EXTERNAL_DATASETS to enable (BETA)."
            )
        from data_analysis_agent.tools.connectors.postgres import PostgresConnector
        return PostgresConnector(server, tables)
    raise DatasetConnectionError(f"Unsupported dataset type: {dtype!r}")
