from datetime import datetime
from pydantic import BaseModel


class DatasetResponse(BaseModel):
    dataset_id: str
    session_id: str
    original_filename: str
    table_name: str
    file_format: str
    row_count: int
    registered_at: datetime

    model_config = {"from_attributes": True}
