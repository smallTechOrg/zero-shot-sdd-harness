from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class DatasetUploadResponse(BaseModel):
    dataset_id: str
    filename: str
    row_count: int
    column_names: list[str]


class DatasetListItem(BaseModel):
    dataset_id: str
    filename: str
    row_count: Optional[int]
    column_names: list[str]
    uploaded_at: datetime
