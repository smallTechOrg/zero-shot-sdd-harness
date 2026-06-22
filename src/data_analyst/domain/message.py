from datetime import datetime
from typing import Any
from pydantic import BaseModel


class MessageResponse(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    sql: str | None = None
    results: list[dict[str, Any]] | None = None
    token_usage: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
