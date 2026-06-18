from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    ready = "ready"
    error = "error"


class Role(str, Enum):
    user = "user"
    assistant = "assistant"


class Session(BaseModel):
    id: str
    filename: str
    file_path: str
    file_size_bytes: int
    row_count: int
    column_names: list[str]
    column_dtypes: dict[str, str]
    status: SessionStatus = SessionStatus.ready
    error_message: str | None = None
    created_at: datetime
    last_active_at: datetime


class Message(BaseModel):
    id: str
    session_id: str
    role: Role
    content: str
    reasoning_trace: list[dict[str, Any]] | None = None
    iteration_count: int | None = None
    created_at: datetime


class Run(BaseModel):
    id: str
    session_id: str
    status: str = "running"
    final_answer: str | None = None
    action_history: list[dict[str, Any]] = Field(default_factory=list)
    tokens_input: int = 0
    tokens_output: int = 0
    estimated_cost_usd: float | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
