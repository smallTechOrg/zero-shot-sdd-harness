import uuid
from pathlib import Path

import duckdb

SUPPORTED_TYPES = {"csv", "excel", "json", "parquet"}


def _build_read_expr(file_path: str, file_type: str) -> str:
    """Return the DuckDB read expression for a given file path and type."""
    if file_type == "csv":
        return f"read_csv_auto('{file_path}')"
    elif file_type == "excel":
        # Excel converted to tmp CSV at ingest time; file_path already points to the csv
        return f"read_csv_auto('{file_path}')"
    elif file_type == "json":
        return f"read_json_auto('{file_path}')"
    elif file_type == "parquet":
        return f"read_parquet('{file_path}')"
    raise ValueError(f"Unsupported file type: {file_type}")


def ingest_file(conn: duckdb.DuckDBPyConnection, file_path: str, name: str) -> dict:
    """Load a file into DuckDB, register it as a named view, record in datasets table."""
    path = Path(file_path)
    suffix = path.suffix.lower().lstrip(".")
    file_type = "excel" if suffix in ("xlsx", "xls") else suffix

    if file_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported file type: {suffix}")

    if file_type == "excel":
        import pandas as pd

        tmp_csv = str(path.with_suffix("")) + "_tmp.csv"
        pd.read_excel(file_path).to_csv(tmp_csv, index=False)
        read_expr = _build_read_expr(tmp_csv, "csv")
    else:
        read_expr = _build_read_expr(file_path, file_type)

    # Get schema info (column names)
    df = conn.execute(f"SELECT * FROM {read_expr} LIMIT 1").fetchdf()
    columns = list(df.columns)

    # Count rows
    row_count = conn.execute(f"SELECT COUNT(*) FROM {read_expr}").fetchone()[0]

    # Create a persistent view so the dataset can be queried by name
    conn.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM {read_expr}")

    # Register in datasets table
    dataset_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO datasets (id, name, file_path, file_type, row_count, column_names)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [dataset_id, name, file_path, file_type, row_count, columns],
    )

    return {
        "id": dataset_id,
        "name": name,
        "file_type": file_type,
        "row_count": row_count,
        "columns": columns,
    }
