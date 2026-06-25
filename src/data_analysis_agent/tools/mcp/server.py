from __future__ import annotations

import re
from pathlib import Path

import duckdb
from mcp.server.fastmcp import FastMCP

DEFAULT_MAX_ROWS = 200

# Statement types that must never run via the read-only query path (R-SQLi). A query that starts
# with SELECT/WITH and contains no statement separator cannot BE one of these, but we reject the
# keywords defensively. (Common column names are not in this set, so no false positives.)
_FORBIDDEN = ("ATTACH", "DETACH", "COPY", "PRAGMA", "INSTALL", "LOAD", "EXPORT", "IMPORT")
_WORD = re.compile(r"[A-Za-z_]+")


class RecoverableQueryError(ValueError):
    """A query problem the LLM can fix by retrying.

    FastMCP turns any exception raised inside a tool into a ``CallToolResult`` with
    ``isError=True``, so raising this is how a recoverable error (bad SQL, non-SELECT)
    is surfaced to the agent for self-correction.
    """


def _guard_select(query: str) -> str:
    """Validate a read-only single-statement SELECT/WITH; return the trimmed SQL or raise."""
    q = query.strip().rstrip(";").strip()
    if not q:
        raise RecoverableQueryError("Empty query.")
    if ";" in q:
        raise RecoverableQueryError("Only a single statement is allowed (no ';').")
    upper = q.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        raise RecoverableQueryError(f"Only SELECT statements are allowed. Got: {query[:80]}")
    bad = sorted(set(_WORD.findall(upper)) & set(_FORBIDDEN))
    if bad:
        raise RecoverableQueryError(f"Disallowed keyword(s): {', '.join(bad)}. Read-only SELECT only.")
    return q


def _to_csv(cursor, max_rows: int) -> str:
    """Render a DuckDB cursor as a compact CSV string, capped at ``max_rows``."""
    columns = [d[0] for d in cursor.description] if cursor.description else []
    rows = cursor.fetchmany(max_rows)
    lines = [",".join(columns)]
    lines += [",".join("" if v is None else str(v) for v in row) for row in rows]
    return "\n".join(lines)


def _run_select(conn: duckdb.DuckDBPyConnection, query: str, max_rows: int) -> str:
    """Validate and run a SELECT, returning a compact CSV string (``max_rows`` cap)."""
    sql = _guard_select(query)
    try:
        cursor = conn.execute(sql)
    except duckdb.Error as exc:
        raise RecoverableQueryError(str(exc))
    return _to_csv(cursor, max_rows)


def _run_select_params(
    conn: duckdb.DuckDBPyConnection, query: str, params: dict | list | None, max_rows: int
) -> str:
    """Validate and run a parameter-bound SELECT (canned tools); params bind via DuckDB, never f-strings."""
    sql = _guard_select(query)
    try:
        cursor = conn.execute(sql, params) if params else conn.execute(sql)
    except duckdb.Error as exc:
        raise RecoverableQueryError(str(exc))
    return _to_csv(cursor, max_rows)


# --- Per-server (multi-table) DuckDB-backed MCP server ----------------------
# A connector opens ONE DuckDB connection with all of the server's tables as views, then calls
# build_server to expose a single generic `query` tool. All tables share the connection, so a
# query may JOIN the server's other tables. (The generated GET-API tools live in the DB and are
# served by tools/mcp/dispatch.py, NOT here.)

def new_connection() -> duckdb.DuckDBPyConnection:
    """Return a fresh in-memory DuckDB connection (the caller registers views / ATTACHes)."""
    return duckdb.connect(database=":memory:")


def register_parquet_view(conn: duckdb.DuckDBPyConnection, table_name: str, parquet_path: str | None) -> None:
    """Register a Parquet file as a read-only view named ``table_name`` on ``conn``."""
    if not parquet_path or not Path(parquet_path).exists():
        raise FileNotFoundError(f"Parquet file not found for table {table_name!r}: {parquet_path!r}")
    safe_path = parquet_path.replace("'", "''")
    safe_table = table_name.replace('"', '""')
    conn.execute(f'CREATE VIEW "{safe_table}" AS SELECT * FROM read_parquet(\'{safe_path}\')')


def build_server(
    server_name: str,
    conn: duckdb.DuckDBPyConnection,
    tables: list[dict],
    max_rows: int = DEFAULT_MAX_ROWS,
) -> FastMCP:
    """Build one in-process MCP server exposing a generic read-only ``query`` tool over ``conn``.

    Args:
        server_name: The MCP-server (agent tool) name — used as the server label.
        conn: A DuckDB connection where every table is already a view (parquet views or ATTACH).
        tables: Dicts with ``table_name`` (and optional ``column_names``).
        max_rows: Row cap per query.

    Returns:
        A :class:`FastMCP` server with the connection attached as ``server._duckdb_conn``.
    """
    server = FastMCP(f"mcpserver::{server_name}")
    table_names = [t["table_name"] for t in tables]
    server.add_tool(
        _make_query(conn, max_rows),
        name="query",
        description=_generic_tool_description(table_names),
    )
    server._duckdb_conn = conn  # type: ignore[attr-defined]
    server._table_names = table_names  # type: ignore[attr-defined]
    return server


def _make_query(conn: duckdb.DuckDBPyConnection, max_rows: int):
    """Return a ``query(query: str) -> str`` tool fn bound to a server's DuckDB connection."""
    def query(query: str) -> str:
        """Run a read-only SQL SELECT against this server's tables and return CSV rows."""
        return _run_select(conn, query, max_rows)
    return query


def _generic_tool_description(table_names: list[str]) -> str:
    """Describe the generic query tool, naming the JOINable tables."""
    tables = ", ".join(table_names) or "(none)"
    return f"Run a read-only SQL SELECT over this server's tables ({tables}); you may JOIN them."
