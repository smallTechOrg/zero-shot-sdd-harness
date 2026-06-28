"""Local DuckDB analysis engine.

Pure, local, no LLM calls. Owns CSV ingest into a local DuckDB file, schema
extraction, dataset profiling (bounded aggregate-only health summary), and
dialect-safe local SQL execution.

Privacy boundary: nothing here sends data anywhere. DuckDB holds and queries
the full dataset locally; only the small, bounded result rows requested by the
caller are returned. The schema/profile helpers return aggregate metadata only
(column names, types, counts, numeric min/max) — never raw rows.

Dialect safety: ``execute_sql`` surfaces the exact DuckDB error text in the
raised exception so the agent graph's retry loop can feed it back to the model
(e.g. ``Catalog Error: Scalar Function with name julianday does not exist``).
"""
from __future__ import annotations

import duckdb

# DuckDB types DuckDB classifies as numeric (used to decide min/max + chart axes).
_NUMERIC_TYPE_PREFIXES = (
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "HUGEINT",
    "UTINYINT",
    "USMALLINT",
    "UINTEGER",
    "UBIGINT",
    "UHUGEINT",
    "FLOAT",
    "DOUBLE",
    "DECIMAL",
    "REAL",
)


def _is_numeric_type(duckdb_type: str) -> bool:
    return duckdb_type.upper().startswith(_NUMERIC_TYPE_PREFIXES)


def _quote_ident(name: str) -> str:
    """Quote an identifier for DuckDB (tolerates spaces / symbols / reserved words)."""
    return '"' + name.replace('"', '""') + '"'


def ingest_csv(csv_path: str, duckdb_path: str, table_name: str = "t") -> None:
    """Load a CSV into a local on-disk DuckDB file as ``table_name``.

    Uses DuckDB's native ``read_csv_auto`` with settings tuned for messy,
    real-world CSVs: full-file type sampling, error tolerance, and null padding
    so inconsistent or short rows don't hard-fail ingest. The full data is
    persisted to the DuckDB file at ``duckdb_path`` and never leaves the machine.

    Raises a clear exception (carrying the DuckDB error text) if the file cannot
    be parsed at all.
    """
    con = duckdb.connect(duckdb_path)
    try:
        con.execute(f"DROP TABLE IF EXISTS {_quote_ident(table_name)}")
        con.execute(
            f"CREATE TABLE {_quote_ident(table_name)} AS "
            "SELECT * FROM read_csv_auto(?, "
            "sample_size=-1, "          # scan the whole file for robust type inference
            "all_varchar=false, "
            "ignore_errors=true, "      # skip individually broken lines, don't abort
            "null_padding=true, "       # short rows get NULLs instead of failing
            "header=true)",
            [csv_path],
        )
    except duckdb.Error as exc:  # pragma: no cover - exercised via API ingest path
        raise RuntimeError(f"DuckDB ingest failed: {exc}") from exc
    finally:
        con.close()


def extract_schema(duckdb_path: str, table_name: str = "t") -> dict:
    """Return column names + DuckDB types for the table. NO rows.

    Shape: ``{"columns": [{"name": str, "type": str}, ...]}`` — the schema that
    is safe to send to the LLM (no data values).
    """
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        rows = con.execute(
            f"DESCRIBE {_quote_ident(table_name)}"
        ).fetchall()
    finally:
        con.close()
    # DESCRIBE columns: column_name, column_type, null, key, default, extra
    columns = [{"name": r[0], "type": r[1]} for r in rows]
    return {"columns": columns}


def profile_dataset(duckdb_path: str, table_name: str = "t") -> dict:
    """Compute a bounded, aggregate-only health summary for the table.

    Shape::

        {
          "row_count": int,
          "columns": [
            {"name": str, "type": str, "nulls": int, "distinct": int,
             "min": <num>, "max": <num>},   # min/max only for numeric columns
            ...
          ]
        }

    All values are aggregates — NO raw rows are returned.
    """
    schema = extract_schema(duckdb_path, table_name)
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        tbl = _quote_ident(table_name)
        row_count = con.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0]

        columns: list[dict] = []
        for col in schema["columns"]:
            name = col["name"]
            ident = _quote_ident(name)
            nulls, distinct = con.execute(
                f"SELECT count(*) - count({ident}), count(DISTINCT {ident}) FROM {tbl}"
            ).fetchone()
            entry: dict = {
                "name": name,
                "type": col["type"],
                "nulls": int(nulls),
                "distinct": int(distinct),
            }
            if _is_numeric_type(col["type"]):
                lo, hi = con.execute(
                    f"SELECT min({ident}), max({ident}) FROM {tbl}"
                ).fetchone()
                # cast Decimal → float so the profile JSON-serialises cleanly
                entry["min"] = None if lo is None else float(lo)
                entry["max"] = None if hi is None else float(hi)
            columns.append(entry)
    finally:
        con.close()

    return {"row_count": int(row_count), "columns": columns}


def execute_sql(duckdb_path: str, sql: str, table_name: str = "t") -> dict:
    """Run generated DuckDB SQL LOCALLY against the table and return the result.

    ``table_name`` is accepted for symmetry/forward-compat; the generated SQL is
    expected to reference the table by name (default ``t``).

    Returns the FULL local result: ``{"columns": [...], "rows": [[...], ...]}``.
    The full result stays local — the caller decides what (bounded) slice goes
    to the LLM (see :func:`analysis.charts.to_aggregate`).

    On failure raises ``RuntimeError`` whose message carries the exact DuckDB
    error text (e.g. ``Catalog Error: Scalar Function with name julianday does
    not exist``) so the agent graph can feed it back into the retry loop.
    """
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        cur = con.execute(sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = [list(r) for r in cur.fetchall()]
    except duckdb.Error as exc:
        raise RuntimeError(str(exc)) from exc
    finally:
        con.close()
    return {"columns": columns, "rows": rows}
