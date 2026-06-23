import io
import json
from uuid import uuid4

import pandas as pd
from pandas.api import types as ptypes

from db.models import DatasetRow
from db.session import _get_engine, create_db_session

from data import audit


def _infer_type(series: pd.Series) -> str:
    if ptypes.is_integer_dtype(series):
        return "INTEGER"
    if ptypes.is_float_dtype(series):
        return "REAL"
    if ptypes.is_bool_dtype(series):
        return "INTEGER"
    return "TEXT"


def ingest_file(file_bytes: bytes, filename: str, session_id: str) -> dict:
    """Read CSV/Excel, create SQLite table ds_<dataset_id>, insert rows,
    write a datasets row + an audit_log(operation='ingest') row.
    Returns {dataset_id, table_name, row_count, columns: [{name,type}]}."""
    if not file_bytes:
        raise ValueError("Uploaded file is empty.")

    name = (filename or "").lower()
    try:
        if name.endswith(".xlsx") or name.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(file_bytes))
        elif name.endswith(".csv") or not name:
            df = pd.read_csv(io.BytesIO(file_bytes))
        else:
            df = pd.read_csv(io.BytesIO(file_bytes))
    except ValueError:
        raise
    except Exception as exc:  # pandas raises a variety of parse errors
        raise ValueError(f"Could not parse file '{filename}': {exc}") from exc

    if df.shape[1] == 0:
        raise ValueError("File has zero columns.")
    if df.shape[0] == 0:
        raise ValueError("File has no data rows.")

    columns = [{"name": str(col), "type": _infer_type(df[col])} for col in df.columns]

    dataset_id = str(uuid4())
    table_name = f"ds_{dataset_id.replace('-', '')}"

    engine = _get_engine()
    try:
        df.to_sql(table_name, con=engine, index=False, if_exists="fail")
    except Exception as exc:
        audit.log_operation(
            session_id=session_id,
            operation="ingest",
            question=None,
            sql_text=None,
            rows_returned=None,
            success=False,
            error_message=str(exc),
        )
        raise

    row_count = int(df.shape[0])

    with create_db_session() as session:
        session.add(
            DatasetRow(
                id=dataset_id,
                session_id=session_id,
                table_name=table_name,
                original_filename=filename,
                row_count=row_count,
                columns_json=json.dumps(columns),
            )
        )

    audit.log_operation(
        session_id=session_id,
        operation="ingest",
        question=None,
        sql_text=None,
        rows_returned=row_count,
        success=True,
        error_message=None,
    )

    return {
        "dataset_id": dataset_id,
        "table_name": table_name,
        "row_count": row_count,
        "columns": columns,
    }
