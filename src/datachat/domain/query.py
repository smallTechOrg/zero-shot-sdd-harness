from datetime import datetime
from pydantic import BaseModel


class QueryCreate(BaseModel):
    upload_id: str
    question: str


class Query(BaseModel):
    id: str
    upload_id: str
    question: str
    answer: str
    created_at: datetime

    model_config = {"from_attributes": True}
