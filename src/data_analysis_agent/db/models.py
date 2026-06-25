import json
from datetime import datetime, timezone
from urllib.parse import quote
from uuid import uuid4

from sqlalchemy import Float, Text, TIMESTAMP, Integer, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    """Return a new random UUID string for use as a primary-key default."""
    return str(uuid4())


def _now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class DataSourceRow(Base):
    """A Dataset (the agent's "tool"): a named, URI-addressed collection of tables.

    Reused as the Dataset row. ``name`` is the dataset name (= logical DB name = LLM tool
    canonical name); ``type`` is the dataset type (``parquet`` | ``postgresql``). The per-table
    columns below (``parquet_path``/``row_count``/``column_names_json``/``schema_json``/
    ``capability_description``) are DEPRECATED — table data now lives in ``DatasetTableRow``
    children — kept nullable for safe rollback.
    """

    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False, default="parquet")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    connection_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    # Deprecated per-source columns (data moved to DatasetTableRow); kept nullable for rollback.
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    parquet_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_names_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    capability_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def dataset_uri(self) -> str:
        """The dataset URI, default-deriving an internal ``parquet:///{name}`` when unset."""
        return self.uri or f"parquet:///{quote(self.name or '', safe='')}"

    @property
    def column_names(self) -> list[str]:
        """Decode the JSON-encoded list of column names (empty list if unset)."""
        if self.column_names_json:
            return json.loads(self.column_names_json)
        return []

    @column_names.setter
    def column_names(self, value: list[str]) -> None:
        """Encode and store the list of column names as JSON."""
        self.column_names_json = json.dumps(value)

    @property
    def schema(self) -> list[dict]:
        """Column schema with dtype and nullability: [{name, dtype, nullable}]."""
        if self.schema_json:
            return json.loads(self.schema_json)
        return []


class DatasetTableRow(Base):
    """One table within a Dataset — one Parquet file (parquet) or one introspected table (external).

    The dataset's MCP server exposes one ``query_{table_name}`` capability per row.
    """

    __tablename__ = "dataset_tables"
    __table_args__ = (UniqueConstraint("dataset_id", "table_name", name="uq_dataset_table"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    dataset_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    table_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    parquet_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_names_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    capability_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )

    @property
    def column_names(self) -> list[str]:
        """Decode the JSON-encoded list of column names (empty list if unset)."""
        if self.column_names_json:
            return json.loads(self.column_names_json)
        return []

    @column_names.setter
    def column_names(self, value: list[str]) -> None:
        """Encode and store the list of column names as JSON."""
        self.column_names_json = json.dumps(value)

    @property
    def schema(self) -> list[dict]:
        """Column schema with dtype and nullability: [{name, dtype, nullable}]."""
        if self.schema_json:
            return json.loads(self.schema_json)
        return []


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class SessionDataSourceRow(Base):
    __tablename__ = "session_data_sources"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    data_source_id: Mapped[str] = mapped_column(Text, primary_key=True)


class QueryRecordRow(Base):
    __tablename__ = "query_records"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    iteration_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    query_history_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    api_request_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    @property
    def query_history(self) -> list[dict]:
        """Decode the JSON-encoded tool-call trace into a list of dicts."""
        if self.query_history_json:
            return json.loads(self.query_history_json)
        return []


class AgentRunRow(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    query_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )
