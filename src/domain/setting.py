from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Setting(BaseModel):
    """Public read shape of a `SettingRow` (key/value app setting)."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str | None = None
    updated_at: datetime
