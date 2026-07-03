from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    null_count: int
    sample_values: list[Any] = []


class DatasetProfile(BaseModel):
    columns: list[ColumnProfile] = []
    quality_flags: list[str] = []
    sample_rows: list[dict[str, Any]] = []


class DatasetOut(BaseModel):
    id: str
    name: str
    row_count: int
    column_count: int
    file_format: str
    profile: DatasetProfile


class DatasetSummary(BaseModel):
    id: str
    name: str
    row_count: int
    column_count: int
    created_at: datetime
