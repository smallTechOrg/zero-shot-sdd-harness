from __future__ import annotations

from pathlib import Path

import duckdb
from mcp.server.fastmcp import FastMCP

DEFAULT_MAX_ROWS = 200


class RecoverableQueryError(ValueError):
    """A query problem the LLM can fix by retrying.

    FastMCP turns any exception raised inside a tool into a ``CallToolResult`` with
    ``isError=True``, so raising this is how a recoverable error (bad SQL, non-SELECT)
    is surfaced to the agent for self-correction.
    """


def build_server(
    source: dict, capability_description: str, max_rows: int = DEFAULT_MAX_ROWS
) -> FastMCP:
    """Build an in-process MCP server that wraps ONE Parquet file via DuckDB.

    The server exposes a single read-only ``run_query`` tool. The Parquet is
    registered as a DuckDB view named ``source['table_name']`` so the SQL the LLM
    writes matches the table name advertised in the planning prompt.

    Args:
        source: Serialised data-source dict with ``table_name`` and ``parquet_path``.
        capability_description: Description shown to the LLM for the ``run_query`` tool.
        max_rows: Maximum number of result rows returned per query.

    Returns:
        A configured :class:`FastMCP` server (not yet connected to a client). The
        backing DuckDB connection is attached as ``server._duckdb_conn`` so the
        caller can close it when the run ends.

    Raises:
        FileNotFoundError: If the source has no readable Parquet file (fatal — the
            agent cannot answer without data).
    """
    table = source["table_name"]
    conn = _open_view(source.get("parquet_path"), table)

    server = FastMCP(f"csv::{table}")

    def run_query(query: str) -> str:
        """Run a read-only SQL SELECT against this dataset and return CSV rows."""
        return _run_select(conn, query, max_rows)

    server.add_tool(run_query, name="run_query", description=capability_description)
    server._duckdb_conn = conn  # type: ignore[attr-defined]
    return server


def _open_view(parquet_path: str | None, table: str) -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB connection with the Parquet registered as a view."""
    if not parquet_path or not Path(parquet_path).exists():
        raise FileNotFoundError(
            f"Parquet file not found for table {table!r}: {parquet_path!r}"
        )
    conn = duckdb.connect(database=":memory:")
    safe_path = parquet_path.replace("'", "''")
    safe_table = table.replace('"', '""')
    # DuckDB DDL cannot take bind parameters; the path is server-generated and escaped.
    conn.execute(f'CREATE VIEW "{safe_table}" AS SELECT * FROM read_parquet(\'{safe_path}\')')
    return conn


def _run_select(conn: duckdb.DuckDBPyConnection, query: str, max_rows: int) -> str:
    """Validate and run a SELECT, returning a compact CSV string (``max_rows`` cap)."""
    if not query.strip().upper().startswith("SELECT"):
        raise RecoverableQueryError(f"Only SELECT statements are allowed. Got: {query[:80]}")
    try:
        cursor = conn.execute(query)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(max_rows)
    except duckdb.Error as exc:
        raise RecoverableQueryError(str(exc))
    lines = [",".join(columns)]
    lines += [",".join("" if v is None else str(v) for v in row) for row in rows]
    return "\n".join(lines)
