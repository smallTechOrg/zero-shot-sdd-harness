import json
import re
import logging
from dataclasses import dataclass, field
from typing import Any

from data_analyst.duckdb_service import DuckDBService

logger = logging.getLogger(__name__)

# Destructive SQL guard — regex covers all blocked statement types
_DESTRUCTIVE = re.compile(
    r"^\s*(DROP|DELETE|TRUNCATE|ALTER|INSERT|UPDATE|CREATE|REPLACE|MERGE|UPSERT|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def is_destructive(sql: str) -> bool:
    """Return True if the SQL starts with a destructive statement keyword."""
    return bool(_DESTRUCTIVE.match(sql.strip()))


@dataclass
class TurnState:
    session_id: str
    datasets: list[Any]  # list of Dataset ORM objects
    duckdb_svc: DuckDBService
    result_tables: list[list[dict]] = field(default_factory=list)  # accumulated results from execute_sql
    sql_calls: list[str] = field(default_factory=list)  # all SQL executed this turn
    tables_touched: set[str] = field(default_factory=set)  # table names touched this turn
    row_count_returned: int = 0


def get_tool_definitions() -> list[dict]:
    """Return tool definitions as a list of dicts (used to build google-genai FunctionDeclarations)."""
    return [
        {
            "name": "list_tables",
            "description": "List all available dataset table names that can be queried.",
            "parameters": {
                "type": "OBJECT",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "describe_table",
            "description": "Get the schema (column names and types) for a specific table.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "table_name": {
                        "type": "STRING",
                        "description": "The name of the table to describe.",
                    }
                },
                "required": ["table_name"],
            },
        },
        {
            "name": "execute_sql",
            "description": (
                "Execute a SQL SELECT query against the available datasets. "
                "Returns up to 1000 rows. Only SELECT queries are allowed."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "sql": {
                        "type": "STRING",
                        "description": (
                            "A SQL SELECT query to execute. "
                            "Must not contain DROP, DELETE, TRUNCATE, ALTER, INSERT, UPDATE, CREATE."
                        ),
                    }
                },
                "required": ["sql"],
            },
        },
        {
            "name": "get_sample_rows",
            "description": "Get a sample of rows from a table to understand its data.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "table_name": {
                        "type": "STRING",
                        "description": "The name of the table to sample.",
                    },
                    "n": {
                        "type": "INTEGER",
                        "description": "Number of rows to return (default 5, max 20).",
                    },
                },
                "required": ["table_name"],
            },
        },
    ]


def dispatch_tool_call(name: str, args: dict, state: TurnState) -> dict:
    """Execute a tool call and return the result as a dict."""
    svc = state.duckdb_svc

    if name == "list_tables":
        tables = svc.list_tables()
        return {"tables": tables}

    elif name == "describe_table":
        table_name = args.get("table_name", "")
        try:
            columns = svc.describe_table(table_name)
            return {"table_name": table_name, "columns": columns}
        except Exception as e:
            return {"error": f"Table '{table_name}' not found or cannot be described: {e}"}

    elif name == "execute_sql":
        sql = args.get("sql", "").strip()
        if is_destructive(sql):
            return {
                "rows": [],
                "row_count": 0,
                "error": "Destructive SQL is not permitted. Only SELECT statements are allowed.",
            }
        try:
            rows = svc.execute_query(sql)
            # Cap at 1000 rows
            was_truncated = len(rows) > 1000
            capped = rows[:1000]
            # Track what was queried
            state.sql_calls.append(sql)
            # Extract table names from the SQL (simple regex)
            for tname in _extract_table_names(sql):
                state.tables_touched.add(tname)
            state.row_count_returned = len(capped)
            if capped:
                state.result_tables.append(capped)
            return {"rows": capped, "row_count": len(capped), "truncated": was_truncated, "error": None}
        except Exception as e:
            logger.warning("execute_sql failed: %s", e)
            return {"rows": [], "row_count": 0, "error": f"SQL execution failed: {e}"}

    elif name == "get_sample_rows":
        table_name = args.get("table_name", "")
        n = min(int(args.get("n", 5)), 20)
        try:
            rows = svc.get_sample_rows(table_name, n)
            return {"table_name": table_name, "rows": rows}
        except Exception as e:
            return {"error": f"Could not sample from '{table_name}': {e}"}

    else:
        return {"error": f"Unknown tool: {name}"}


def _extract_table_names(sql: str) -> list[str]:
    """Extract table names from a SQL query (simple regex, best-effort)."""
    from_pattern = re.compile(r"\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)
    join_pattern = re.compile(r"\bJOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)
    names = from_pattern.findall(sql) + join_pattern.findall(sql)
    return list(set(n.lower() for n in names))
