from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class Dataset(BaseModel):
    """Public read shape of a `DatasetRow` (uploaded or derived)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_path: str
    row_count: int
    col_count: int
    columns_json: list[Any]
    content_hash: str
    format: str
    context: str | None = None
    origin: str
    derived_from_run_id: str | None = None
    derived_from_dataset_ids: list[str] | None = None
    derivation_code: str | None = None
    parquet_path: str | None = None
    auto_notes_status: str | None = None
    context_facts: list[Any] | None = None
    created_at: datetime
    updated_at: datetime
