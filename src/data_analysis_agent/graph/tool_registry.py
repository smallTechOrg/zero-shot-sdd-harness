from __future__ import annotations

from data_analysis_agent.db.models import DataSourceRow, SessionDataSourceRow
from data_analysis_agent.db.session import create_db_session
from data_analysis_agent.tools.table_naming import sql_table_name

# Phase-1 shim: the `tools`/`tool_capabilities` tables are gone (their content now
# lives as `tool_description`/`capability_description` columns on DataSource and,
# from Phase 3, is served by the per-source MCP server). Until the async/MCP graph
# lands, this module synthesises the legacy nested tool shape from those columns so
# the existing sync pipeline keeps working unchanged.


def load_tool_registry(session_id: str) -> tuple[list[dict], list[dict]]:
    """Load the session's data sources and synthesise their tool descriptors.

    Args:
        session_id: The session whose attached resources should be loaded.

    Returns:
        A ``(tools, data_sources)`` tuple of JSON-serialisable dicts.
    """
    with create_db_session() as db:
        source_ids = _attached_source_ids(db, session_id)
        rows = [db.get(DataSourceRow, sid) for sid in source_ids]
        rows = [r for r in rows if r is not None]
        sources = [_serialize_source(r) for r in rows]
        tools = [_synthesize_tool(r) for r in rows]
        return tools, sources


def _attached_source_ids(db, session_id: str) -> list[str]:
    """Return the data source ids linked to a session via the join table."""
    links = (
        db.query(SessionDataSourceRow)
        .filter(SessionDataSourceRow.session_id == session_id)
        .all()
    )
    return [link.data_source_id for link in links]


def _serialize_source(ds: DataSourceRow) -> dict:
    """Convert a data source row into a plain dict for AgentState."""
    return {
        "id": ds.id,
        "name": ds.name,
        "type": ds.type,
        "file_path": ds.file_path,
        "parquet_path": ds.parquet_path,
        "column_names": ds.column_names,
        "row_count": ds.row_count,
        "tool_description": ds.tool_description,
        "capability_description": ds.capability_description,
    }


def _synthesize_tool(ds: DataSourceRow) -> dict:
    """Build the legacy nested tool dict for a source from its description columns."""
    table = sql_table_name(ds.name)
    tool_desc = ds.tool_description or f"Execute SQL SELECT queries against '{ds.name}' (table: {table})."
    cap_desc = ds.capability_description or (
        f"Execute a SQL SELECT statement against '{ds.name}'. Table name is '{table}'."
    )
    return {
        "name": "csv_query",
        "type": "csv_query",
        "description": tool_desc,
        "config": {},
        "data_source_id": ds.id,
        "capabilities": [
            {
                "name": "run_query",
                "description": cap_desc,
                "parameter_schema": {
                    "query": {
                        "type": "string",
                        "description": f"A valid SQL SELECT statement. Table name is '{table}'.",
                    }
                },
            }
        ],
    }
