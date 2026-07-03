"""Load an uploaded spreadsheet into a pandas DataFrame.

Pure I/O helpers: no DB, no LLM, no settings. Kept dependency-free so the
subprocess executor can reuse the same loading logic.
"""
from __future__ import annotations

import os

import pandas as pd

CSV_FORMAT = "csv"
XLSX_FORMAT = "xlsx"
SUPPORTED_FORMATS = (CSV_FORMAT, XLSX_FORMAT)

# Extension -> canonical format.
_EXTENSION_MAP = {
    ".csv": CSV_FORMAT,
    ".xlsx": XLSX_FORMAT,
    ".xls": XLSX_FORMAT,
}


def detect_format(filename: str) -> str:
    """Return ``"csv"`` or ``"xlsx"`` from a filename's extension.

    Raises ``ValueError`` for an unsupported/missing extension.
    """
    if not filename:
        raise ValueError("Cannot detect file format: empty filename.")
    _, ext = os.path.splitext(filename)
    fmt = _EXTENSION_MAP.get(ext.lower())
    if fmt is None:
        raise ValueError(
            f"Unsupported file type '{ext or filename}'. "
            f"Supported extensions: .csv, .xlsx."
        )
    return fmt


def load_dataframe(file_path: str, file_format: str) -> pd.DataFrame:
    """Read a stored file into a DataFrame.

    ``file_format`` must be one of ``SUPPORTED_FORMATS``. Reads with pandas
    defaults (efficient enough for ~100 MB / hundreds of thousands of rows).
    Raises ``ValueError`` on an unsupported format or an unparseable/empty file.
    """
    fmt = (file_format or "").lower()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported file format '{file_format}'. "
            f"Expected one of {SUPPORTED_FORMATS}."
        )

    try:
        if fmt == CSV_FORMAT:
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path, engine="openpyxl")
    except FileNotFoundError:
        raise
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"File is empty or has no parseable data: {file_path}") from exc
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface any parser failure as ValueError
        raise ValueError(
            f"Could not parse {fmt} file '{file_path}': {exc}"
        ) from exc

    if df.shape[1] == 0:
        raise ValueError(f"File has no columns: {file_path}")

    return df
