import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from analyst.domain.session import ColumnDef, DatasetMeta, Session
from analyst.errors import AnalystError

ALLOWED_EXTENSIONS = {".csv", ".json"}


def _normalise_table_name(filename: str) -> str:
    """Strip extension, lowercase, replace spaces and hyphens with underscores."""
    stem = Path(filename).stem
    return stem.lower().replace(" ", "_").replace("-", "_")


def validate_file(filename: str, size_bytes: int) -> None:
    """Raise AnalystError for unsupported extension or oversized file."""
    from analyst.config.settings import get_settings

    # Reject filenames that could break SQL string literals or escape the upload directory.
    _INVALID_CHARS = {"'", '"', "/", "\\"}
    if any(c in filename for c in _INVALID_CHARS):
        raise AnalystError(
            "invalid_file",
            "Filename contains invalid characters.",
            400,
        )

    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AnalystError(
            "unsupported_format",
            f"Unsupported file format '{ext}'. Allowed: .csv, .json",
            400,
        )
    if size_bytes > max_bytes:
        raise AnalystError(
            "file_too_large",
            f"File size {size_bytes} bytes exceeds maximum {max_bytes} bytes ({settings.max_upload_mb} MB)",
            400,
        )


def infer_schema(file_path: str, format: str) -> tuple[list[ColumnDef], int]:
    """Use DuckDB to describe the file and return (columns, row_count)."""
    conn = duckdb.connect()
    try:
        if format == "json":
            source = f"read_json_auto('{file_path}')"
        else:
            source = f"'{file_path}'"

        try:
            describe_rows = conn.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()
        except duckdb.Error:
            if format == "json":
                raise AnalystError(
                    "invalid_file",
                    "JSON file is not a top-level array of objects.",
                    400,
                )
            raise AnalystError(
                "invalid_file",
                "CSV file has no header row or cannot be parsed.",
                400,
            )
        except Exception:
            if format == "json":
                raise AnalystError(
                    "invalid_file",
                    "JSON file is not a top-level array of objects.",
                    400,
                )
            raise AnalystError(
                "invalid_file",
                "CSV file has no header row or cannot be parsed.",
                400,
            )

        columns = []
        for row in describe_rows:
            col_name = row[0]
            col_type_raw = row[1].lower()
            # Normalise DuckDB types to simplified names
            if col_type_raw in ("bigint", "integer", "smallint", "tinyint", "hugeint", "ubigint", "uinteger", "usmallint", "utinyint", "int8", "int4", "int2", "int1"):
                col_type = "integer"
            elif col_type_raw in ("double", "float", "real", "decimal", "numeric") or col_type_raw.startswith("decimal"):
                col_type = "float"
            elif col_type_raw in ("boolean", "bool"):
                col_type = "boolean"
            elif col_type_raw in ("date",):
                col_type = "date"
            elif col_type_raw in ("timestamp", "timestamp with time zone", "timestamptz"):
                col_type = "datetime"
            else:
                col_type = "text"
            columns.append(ColumnDef(name=col_name, type=col_type))

        row_count = conn.execute(f"SELECT COUNT(*) FROM {source}").fetchone()[0]
        return columns, row_count
    finally:
        conn.close()


def store_file(upload: bytes, session_id: str, filename: str, data_dir: str) -> str:
    """Write bytes to data_dir/datasets/<session_id>/<filename>. Returns absolute path."""
    dest_dir = Path(data_dir) / "datasets" / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename
    dest_path.write_bytes(upload)
    return str(dest_path.resolve())


def add_dataset_to_session(
    session: Session,
    file_bytes: bytes,
    original_filename: str,
    settings,
) -> DatasetMeta:
    """
    Orchestrate validate, store, infer. Returns DatasetMeta.
    If a dataset with the same original_filename exists, overwrites it (keeps dataset_id).
    """
    validate_file(original_filename, len(file_bytes))

    ext = Path(original_filename).suffix.lower()
    fmt = "json" if ext == ".json" else "csv"
    table_name = _normalise_table_name(original_filename)

    # Check for existing dataset with same filename
    existing = next(
        (d for d in session.datasets if d.original_filename == original_filename),
        None,
    )
    dataset_id = existing.dataset_id if existing is not None else str(uuid.uuid4())

    file_path = store_file(file_bytes, session.session_id, original_filename, settings.data_dir)
    columns, row_count = infer_schema(file_path, fmt)

    meta = DatasetMeta(
        dataset_id=dataset_id,
        name=table_name,
        original_filename=original_filename,
        format=fmt,
        columns=columns,
        row_count=row_count,
        size_bytes=len(file_bytes),
        file_path=file_path,
        uploaded_at=datetime.now(timezone.utc),
    )

    if existing is not None:
        # Replace existing entry
        session.datasets = [
            meta if d.original_filename == original_filename else d
            for d in session.datasets
        ]
    else:
        session.datasets.append(meta)

    return meta
