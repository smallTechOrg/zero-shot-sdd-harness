"""Session-scoped pool of in-process MCP servers — the agent's MCP client layer.

A **session** owns one pool: one in-process MCP server **per attached MCP-server entity**, each
exposing a generic read-only ``query`` tool over that server's tables. Built lazily on the session's
first query and reused. This is the ONLY module that imports ``mcp.shared.memory`` (the in-memory
transport).

Concurrency (see spec/product/07-agent-graph.md):
- LangGraph runs each node in its own asyncio task, so MCP ``ClientSession``s are **transient**
  (opened/closed within a single call). The pool holds only plain objects across nodes/queries:
  the built ``FastMCP`` servers and their DuckDB connections.
- A session's DuckDB connections are not concurrency-safe, so queries on one session are serialized
  by a per-session ``threading.Lock`` (held by ``run_pipeline`` for the whole query). ``close()``
  acquires that lock before teardown so a server change never closes a connection mid-query.
- Pools are idle/LRU-evicted; eviction skips sessions whose lock is currently held (in use).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from importlib.metadata import version

import structlog
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from data_analysis_agent.config.settings import get_settings
from data_analysis_agent.db.models import McpServerRow, SessionMcpServerRow
from data_analysis_agent.db.session import create_db_session
from data_analysis_agent.tools.connectors.base import get_connector

log = structlog.get_logger()

# Relies on the in-memory transport helper, which exists in mcp 1.x and is removed in 2.x.
_MCP_VERSION = version("mcp")
if not _MCP_VERSION.startswith("1."):
    raise RuntimeError(
        f"mcp {_MCP_VERSION} is installed but this code targets the 1.x in-memory transport. "
        f"Pin mcp==1.28.0."
    )

_GENERIC_TOOL = "query"


class NoServersError(Exception):
    """Raised when a session has no attached MCP servers to build a pool from."""


@dataclass
class _Server:
    """One attached MCP-server entity and its in-process FastMCP server (generic SQL tool)."""

    name: str
    server: FastMCP
    description: str
    tables: list[dict]  # [{"table": str, "columns": list[str]}]


@dataclass
class SessionPool:
    """A session's MCP servers, addressed single-level by server ``name``."""

    session_id: str
    servers: dict[str, _Server]
    last_used: float

    def snapshot(self) -> list[dict]:
        """Flat, agent-facing tool list for the planning prompt (one tool per server)."""
        return [
            {
                "tool": s.name,
                "description": s.description,
                "tables": s.tables,
            }
            for s in self.servers.values()
        ]

    async def call_tool(self, tool: str, arguments: dict) -> tuple[str, bool]:
        """Route a single-level call to the server's generic ``query`` tool."""
        s = self.servers.get(tool)
        if s is None:
            valid = ", ".join(self.servers) or "(none)"
            return f"Unknown tool '{tool}'. Valid tools: {valid}.", True
        async with create_connected_server_and_client_session(s.server) as session:
            result = await session.call_tool(_GENERIC_TOOL, arguments)
        text = result.content[0].text if result.content else ""
        return text, bool(result.isError)

    def aclose(self) -> None:
        """Close every server's DuckDB connection (plain, task-safe)."""
        for s in self.servers.values():
            conn = getattr(s.server, "_duckdb_conn", None)
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


class SessionPoolManager:
    """Builds, caches, serializes, and evicts one MCP pool per session."""

    def __init__(self, max_pools: int, idle_seconds: float) -> None:
        self._pools: dict[str, SessionPool] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._registry = threading.Lock()  # guards _pools and _locks
        self._max_pools = max_pools
        self._idle_seconds = idle_seconds

    def session_lock(self, session_id: str) -> threading.Lock:
        """Return the per-session lock (created on first use)."""
        with self._registry:
            lock = self._locks.get(session_id)
            if lock is None:
                lock = self._locks[session_id] = threading.Lock()
            return lock

    async def acquire(self, session_id: str) -> SessionPool:
        """Return the session's pool, building it lazily on first use.

        Call while holding ``session_lock(session_id)``. Raises :class:`NoServersError`
        if the session has no attached servers.
        """
        with self._registry:
            pool = self._pools.get(session_id)
            if pool is not None:
                pool.last_used = time.monotonic()
                return pool

        pool = await self._build(session_id)  # async (list_tools) — outside the registry lock

        with self._registry:
            existing = self._pools.get(session_id)
            if existing is not None:  # built concurrently — keep the first
                pool.aclose()
                existing.last_used = time.monotonic()
                return existing
            self._pools[session_id] = pool
            self._evict_locked()
            log.info("session_pool.built", session_id=session_id, servers=len(pool.servers),
                     active_pools=len(self._pools))
            return pool

    def snapshot(self, session_id: str) -> list[dict]:
        """Return the flat server/tool list for ``plan_action`` (empty if not built)."""
        with self._registry:
            pool = self._pools.get(session_id)
            if pool is None:
                return []
            pool.last_used = time.monotonic()
            return pool.snapshot()

    async def call_tool(self, session_id: str, tool: str, arguments: dict) -> tuple[str, bool]:
        """Route a single-level tool call to the session's pool (must be acquired first)."""
        with self._registry:
            pool = self._pools.get(session_id)
            if pool is not None:
                pool.last_used = time.monotonic()
        if pool is None:
            return f"No MCP pool for session '{session_id}'.", True
        return await pool.call_tool(tool, arguments)

    def close(self, session_id: str) -> None:
        """Close a session's pool, waiting for any in-flight query first. Idempotent.

        Acquires the per-session lock before teardown so a server change (sync/delete) never closes
        a DuckDB connection mid-query on the pipeline thread.
        """
        lock = self.session_lock(session_id)
        with lock:
            with self._registry:
                pool = self._pools.pop(session_id, None)
            if pool is not None:
                pool.aclose()
                log.info("session_pool.closed", session_id=session_id)

    def close_all(self) -> None:
        """Close every pool (on app shutdown)."""
        with self._registry:
            pools = list(self._pools.values())
            self._pools.clear()
        for pool in pools:
            pool.aclose()

    def close_sessions_for_server(self, mcp_server_id: str) -> None:
        """Close the pools of every session attached to a given server (after a change)."""
        with create_db_session() as db:
            links = (
                db.query(SessionMcpServerRow)
                .filter(SessionMcpServerRow.mcp_server_id == mcp_server_id)
                .all()
            )
            session_ids = [link.session_id for link in links]
        for sid in session_ids:
            self.close(sid)

    # ---- internals -------------------------------------------------------

    async def _build(self, session_id: str) -> SessionPool:
        loaded = _load_servers(session_id)
        if not loaded:
            raise NoServersError("No MCP servers attached to this session")
        max_rows = get_settings().mcp_max_result_rows
        servers: dict[str, _Server] = {}
        for server_dict, tables in loaded:
            connector = get_connector(server_dict, tables)
            fast = connector.build_server(max_rows)
            await _verify_server(fast)
            servers[server_dict["name"]] = _Server(
                name=server_dict["name"],
                server=fast,
                description=server_dict.get("description") or "",
                tables=[{"table": t["table_name"], "columns": t.get("column_names") or []} for t in tables],
            )
        return SessionPool(session_id, servers, time.monotonic())

    def _evict_locked(self) -> None:
        """Evict idle + over-cap pools, skipping in-use (locked) sessions. Holds ``_registry``."""
        now = time.monotonic()
        for sid, pool in list(self._pools.items()):
            if now - pool.last_used > self._idle_seconds:
                self._try_close_locked(sid)
        while len(self._pools) > self._max_pools:
            sid = min(self._pools, key=lambda s: self._pools[s].last_used)
            if not self._try_close_locked(sid):
                break

    def _try_close_locked(self, sid: str) -> bool:
        """Close a pool iff its session is not currently in use. Holds ``_registry``."""
        lock = self._locks.get(sid)
        if lock is not None and not lock.acquire(blocking=False):
            return False
        try:
            pool = self._pools.pop(sid, None)
            if pool is not None:
                pool.aclose()
                log.info("session_pool.evicted", session_id=sid)
            return True
        finally:
            if lock is not None:
                lock.release()


async def _verify_server(server: FastMCP) -> None:
    """Open a transient session once to confirm the server exposes the generic ``query`` tool."""
    async with create_connected_server_and_client_session(server) as session:
        listed = await session.list_tools()
    names = {t.name for t in listed.tools}
    if _GENERIC_TOOL not in names:
        raise RuntimeError(f"MCP server is missing the '{_GENERIC_TOOL}' tool (has: {sorted(names)})")


def _load_servers(session_id: str) -> list[tuple[dict, list[dict]]]:
    """Load a session's MCP servers + their physical tables as serialisable ``(server, tables)`` dicts."""
    with create_db_session() as db:
        links = (
            db.query(SessionMcpServerRow)
            .filter(SessionMcpServerRow.session_id == session_id)
            .all()
        )
        loaded: list[tuple[dict, list[dict]]] = []
        for link in links:
            srv = db.get(McpServerRow, link.mcp_server_id)
            if srv is None:
                continue
            tables = srv.physical_tables
            if not tables:
                continue
            loaded.append((_serialize_server(srv), tables))
        return loaded


def _serialize_server(srv: McpServerRow) -> dict:
    return {
        "id": srv.id,
        "name": srv.name,
        "type": srv.type,
        "uri": srv.uri,
        "description": srv.description or srv.title or "",
    }


_manager: SessionPoolManager | None = None


def get_manager() -> SessionPoolManager:
    """Return the process-wide :class:`SessionPoolManager` singleton."""
    global _manager
    if _manager is None:
        s = get_settings()
        _manager = SessionPoolManager(s.max_session_pools, s.session_pool_idle_seconds)
    return _manager
