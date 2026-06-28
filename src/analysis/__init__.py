"""Local DuckDB analysis engine — the public surface used by the agent graph.

All functions are pure and local: they read/write only the on-disk DuckDB file.
No LLM calls; no data leaves the machine. The graph's privacy_guard uses
``to_aggregate``/``AGG_ROW_CAP`` to bound what (if any) result data reaches the
LLM.
"""
from analysis.charts import AGG_ROW_CAP, pick_chart, to_aggregate
from analysis.duckdb_engine import (
    execute_sql,
    extract_schema,
    ingest_csv,
    profile_dataset,
)

__all__ = [
    # ingest + introspection
    "ingest_csv",
    "extract_schema",
    "profile_dataset",
    # local SQL execution (the run_duckdb_sql tool)
    "execute_sql",
    # charting + privacy cap
    "pick_chart",
    "to_aggregate",
    "AGG_ROW_CAP",
]
