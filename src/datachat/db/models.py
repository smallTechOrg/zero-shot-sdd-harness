import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Text, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UploadRow(Base):
    __tablename__ = "uploads"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int] = mapped_column(nullable=False)
    columns_json: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )

    @property
    def columns(self) -> list[str]:
        return json.loads(self.columns_json)


class QueryRow(Base):
    __tablename__ = "queries"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    upload_id: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
