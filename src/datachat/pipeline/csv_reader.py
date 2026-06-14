import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

MAX_SAMPLE_ROWS = 20


def read_csv_metadata(file_path: str) -> tuple[int, list[str]]:
    """Return (row_count, column_names) for the given CSV file."""
    df = pd.read_csv(file_path)
    return len(df), list(df.columns)


def build_query_context(file_path: str) -> str:
    """Build a context string with column names and sample rows for the LLM prompt."""
    df = pd.read_csv(file_path)
    columns = list(df.columns)
    sample = df.head(MAX_SAMPLE_ROWS).to_csv(index=False)
    return (
        f"Columns: {', '.join(columns)}\n\n"
        f"Sample data (up to {MAX_SAMPLE_ROWS} rows):\n{sample}"
    )


def get_upload_path(upload_dir: str, filename: str) -> Path:
    return Path(upload_dir) / filename
