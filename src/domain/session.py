from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationSession(BaseModel):
    """Public read shape of a `ConversationSessionRow`."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str | None = None
    dataset_ids_json: list[str] | None = None
    name: str | None = None
    created_at: datetime
    updated_at: datetime
