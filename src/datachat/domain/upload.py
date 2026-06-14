from datetime import datetime
from pydantic import BaseModel


class UploadCreate(BaseModel):
    filename: str
    original_filename: str
    row_count: int
    columns: list[str]


class Upload(BaseModel):
    id: str
    filename: str
    original_filename: str
    row_count: int
    columns: list[str]
    uploaded_at: datetime

    model_config = {"from_attributes": True}
