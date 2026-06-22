import threading
from typing import Any

import duckdb
import sqlglot
import sqlglot.expressions as exp

from analyst.domain.session import DatasetMeta
from analyst.errors import AnalystError
from analyst.services.dataset_service import _normalise_table_name  # noqa: F401 — re-exported for callers


def register_views(conn: duckdb.DuckDBPyConnection, datasets: list[DatasetMeta]) -> None:
    """Register each dataset as a DuckDB view using the normalised table name."""
    for dataset in datasets:
        if dataset.format == "json":
            source = f"read_json_auto('{dataset.file_path}')"
        else:
            source = f"'{dataset.file_path}'"
        conn.execute(f"CREATE OR REPLACE VIEW {dataset.name} AS SELECT * FROM {source}")


def validate_ast(sql: str) -> None:
    """Parse SQL with sqlglot and verify the root node is a SELECT statement."""
    try:
        parsed = sqlglot.parse_one(sql)
    except Exception as e:
        raise AnalystError("sql_rejected", f"SQL could not be parsed: {e}", 422) from e

    if not isinstance(parsed, exp.Select):
        raise AnalystError(
            "sql_rejected",
            f"Only SELECT statements are allowed. Got: {type(parsed).__name__}",
            422,
        )


def execute_query(sql: str, datasets: list[DatasetMeta], settings: Any) -> dict:
    """
    Execute validated SQL against datasets using DuckDB.
    Returns {columns, rows, row_count, truncated, total_row_count}.
    Enforces row cap and query timeout.
    """
    max_rows = settings.max_result_rows
    timeout_s = settings.query_timeout_s

    conn = duckdb.connect()
    result_container: list = []   # index 0 → result dict or exception
    is_analyst_error: list = []   # non-empty if the exception is an AnalystError

    def _run() -> None:
        try:
            register_views(conn, datasets)
            validate_ast(sql)
            cursor = conn.execute(sql)
            all_rows = cursor.fetchmany(max_rows + 1)
            columns = [desc[0] for desc in cursor.description]
            truncated = len(all_rows) > max_rows
            rows = all_rows[:max_rows]
            if truncated:
                count_cursor = conn.execute(
                    f"SELECT COUNT(*) FROM ({sql}) __count_subq__"
                )
                total_row_count = count_cursor.fetchone()[0]
            else:
                total_row_count = len(rows)
            result_container.append({
                "columns": columns,
                "rows": [list(r) for r in rows],
                "row_count": len(rows),
                "truncated": truncated,
                "total_row_count": total_row_count,
            })
        except AnalystError as e:
            is_analyst_error.append(True)
            result_container.append(e)
        except Exception as e:
            result_container.append(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout=timeout_s)

    if thread.is_alive():
        # Thread-safe interrupt so the running query stops, then close the connection.
        conn.interrupt()
        thread.join(2)
        conn.close()
        raise AnalystError("query_timeout", "Query exceeded time limit.", 504)

    conn.close()

    if not result_container:
        raise AnalystError("query_failed", "Query returned no result", 500)

    outcome = result_container[0]

    if isinstance(outcome, AnalystError):
        raise outcome

    if isinstance(outcome, Exception):
        exc_str = str(outcome).lower()
        exc_type = type(outcome).__name__
        if (
            exc_type in ("CatalogException", "BinderException")
            or ("not found" in exc_str or "does not exist" in exc_str)
        ):
            raise AnalystError(
                "unknown_table",
                f"SQL references a table not in the session: {outcome}",
                422,
            )
        raise AnalystError("query_failed", f"Query execution failed: {outcome}", 500)

    return outcome
