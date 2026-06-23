"""Per-run pool of in-process MCP servers — the agent's MCP client layer.

This is the ONLY module that imports ``mcp.shared.memory`` (the in-memory transport),
so swapping to stdio / Streamable-HTTP / the v2 ``mcp.client.Client`` is a one-file change.

Design (see spec/product/07-agent-graph.md "Async lifecycle"): LangGraph runs each node in
its own asyncio task, and AnyIO binds an async context manager to its entering task. So the
pool holds only **plain, task-safe objects across nodes** — the built ``FastMCP`` servers and
their DuckDB connections — while every ``ClientSession`` is **transient**, opened and closed
within a single call. The pool is kept in a module-level dict keyed by ``run_id`` (mirroring
the old ``data_cache`` pattern); it is not serialisable and never lives in ``AgentState``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import version

from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from data_analysis_agent.graph.mcp.csv_server import DEFAULT_MAX_ROWS, build_server

# This module relies on the in-memory transport helper, which exists in mcp 1.x and is
# removed in the 2.x line. Fail loudly rather than mysteriously if an incompatible major
# is ever installed (the dependency is pinned ==1.28.0, but lockfiles drift).
_MCP_VERSION = version("mcp")
if not _MCP_VERSION.startswith("1."):
    raise RuntimeError(
        f"mcp {_MCP_VERSION} is installed but this code targets the 1.x in-memory transport "
        f"(mcp.shared.memory.create_connected_server_and_client_session). Pin mcp==1.28.0."
    )

_pools: dict[str, "McpPool"] = {}


@dataclass
class _ToolEntry:
    """A discovered tool and the server that backs it."""

    server: FastMCP
    server_tool_name: str  # the tool's name on its server, e.g. "run_query"
    table_name: str
    description: str
    parameter_schema: dict


@dataclass
class McpPool:
    """One run's MCP servers, addressed by namespaced tool key (``<table>__<tool>``)."""

    run_id: str
    _entries: dict[str, _ToolEntry] = field(default_factory=dict)
    _servers: list[FastMCP] = field(default_factory=list)

    async def add_source(self, source: dict, max_rows: int) -> None:
        """Build the server for one source and discover its tools (transient session)."""
        server = build_server(source, source.get("capability_description") or "", max_rows=max_rows)
        self._servers.append(server)
        table = source["table_name"]
        async with create_connected_server_and_client_session(server) as session:
            listed = await session.list_tools()
        for tool in listed.tools:
            self._entries[f"{table}__{tool.name}"] = _ToolEntry(
                server=server,
                server_tool_name=tool.name,
                table_name=table,
                description=tool.description or "",
                parameter_schema=_input_properties(tool.inputSchema),
            )

    def list_tools(self) -> list[dict]:
        """Return the aggregated, agent-facing tool descriptors for ``state['tools']``."""
        return [
            {
                "name": key,
                "table_name": entry.table_name,
                "description": entry.description,
                "parameter_schema": entry.parameter_schema,
            }
            for key, entry in self._entries.items()
        ]

    async def call_tool(self, key: str, arguments: dict) -> tuple[str, bool]:
        """Invoke a namespaced tool via a transient session; return ``(text, is_error)``.

        Unknown tool keys are a recoverable error (the LLM is told the valid keys).
        """
        entry = self._entries.get(key)
        if entry is None:
            valid = ", ".join(self._entries) or "(none)"
            return f"Unknown tool '{key}'. Valid tools: {valid}.", True
        async with create_connected_server_and_client_session(entry.server) as session:
            result = await session.call_tool(entry.server_tool_name, arguments)
        text = result.content[0].text if result.content else ""
        return text, bool(result.isError)

    def aclose(self) -> None:
        """Close every server's DuckDB connection (plain, task-safe)."""
        for server in self._servers:
            conn = getattr(server, "_duckdb_conn", None)
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


def _input_properties(input_schema: dict | None) -> dict:
    """Reduce an MCP ``inputSchema`` to its property map for the planning prompt."""
    if not input_schema:
        return {}
    return input_schema.get("properties", input_schema)


async def open_pool(run_id: str, sources: list[dict], max_rows: int = DEFAULT_MAX_ROWS) -> McpPool:
    """Build one MCP server per source and register the pool under ``run_id``.

    On any failure mid-build, the partially-built pool is closed before re-raising so no
    DuckDB connection leaks (a missing Parquet raises here → fatal for the run).
    """
    pool = McpPool(run_id)
    try:
        for source in sources:
            await pool.add_source(source, max_rows)
    except BaseException:
        pool.aclose()
        raise
    _pools[run_id] = pool
    return pool


def get_pool(run_id: str) -> McpPool | None:
    """Return the pool for a run, or ``None`` if none is registered."""
    return _pools.get(run_id)


async def close_pool(run_id: str) -> None:
    """Close and forget a run's pool; safe to call multiple times (idempotent)."""
    pool = _pools.pop(run_id, None)
    if pool is not None:
        pool.aclose()
