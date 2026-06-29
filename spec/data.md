# Data Model

## Storage Overview

SQLite database at `data/agent.db` (relative to repo root). Three tables: `sessions`, `uploaded_files`, `messages`. All data is session-scoped and ephemeral — no data survives a session deletion. On server startup, any sessions older than 1 hour are cleaned up along with their temp files.

## Entities

### Entity: Session

Represents a single user analysis session. Created when the user opens the app; destroyed on explicit DELETE or expiry.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (UUID v4) | yes | Primary key — unguessable opaque token |
| created_at | TIMESTAMP | yes | UTC timestamp of session creation |
| expires_at | TIMESTAMP | yes | created_at + 1 hour; used by startup cleanup job |

### Entity: UploadedFile

Represents one CSV file uploaded within a session. Stores the file's location on disk and its computed profile. Never stores raw row data.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (UUID v4) | yes | Primary key |
| session_id | TEXT (FK → sessions.id) | yes | Owning session; CASCADE DELETE |
| filename | TEXT | yes | Original filename as provided by the browser (e.g. "sales.csv") |
| temp_path | TEXT | yes | Absolute path to the CSV on disk (e.g. "/tmp/agent_sessions/{session_id}/sales.csv") |
| profile_json | TEXT | yes | JSON blob containing the computed profile (schema below) |
| uploaded_at | TIMESTAMP | yes | UTC timestamp of upload |

**profile_json schema:**
```json
{
  "row_count": 1250,
  "column_count": 8,
  "columns": [
    {
      "name": "revenue",
      "dtype": "float64",
      "null_count": 3,
      "null_pct": 0.24,
      "stats": {"min": 0.0, "max": 99999.9, "mean": 5432.1, "std": 3210.5, "p25": 1200.0, "p50": 4800.0, "p75": 8900.0},
      "sample_values": ["1200.0", "8450.5", "320.0"]
    },
    {
      "name": "region",
      "dtype": "object",
      "null_count": 0,
      "null_pct": 0.0,
      "top_values": {"West": 340, "East": 310, "North": 300, "South": 300},
      "sample_values": ["West", "East", "North"]
    }
  ],
  "quality_flags": [
    {"type": "WARNING", "column": "revenue", "message": "3 null values (0.24%)"},
    {"type": "WARNING", "column": null, "message": "42 duplicate rows detected"}
  ]
}
```

Profile JSON contains ONLY statistical metadata — never raw row values. `sample_values` contains the first 3 non-null stringified cell values per column, which are acceptable as they are illustrative examples, not full row data sent to the LLM.

### Entity: Message

Represents one turn in the conversation (either a user question or an assistant answer).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (UUID v4) | yes | Primary key |
| session_id | TEXT (FK → sessions.id) | yes | Owning session; CASCADE DELETE |
| role | TEXT | yes | "user" or "assistant" |
| content | TEXT | yes | Plain text of the message |
| chart_json | TEXT | no | NULL, or a Plotly figure serialised to JSON string (assistant messages only) |
| created_at | TIMESTAMP | yes | UTC timestamp of message creation |

`chart_json` contains Plotly trace data with aggregated values (e.g. bar heights, line points) produced by the executed pandas code. This is acceptable — it is already aggregated data, not raw row-level values.

## Relationships

```
sessions 1──* uploaded_files   (CASCADE DELETE: deleting a session removes all its files)
sessions 1──* messages          (CASCADE DELETE: deleting a session removes all its messages)
```

## DDL

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE uploaded_files (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    temp_path TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    uploaded_at TIMESTAMP NOT NULL
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    chart_json TEXT,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_uploaded_files_session ON uploaded_files(session_id);
CREATE INDEX idx_messages_session_created ON messages(session_id, created_at);
```

## SQLAlchemy Models

Use SQLAlchemy 2.0 declarative with `Mapped` and `mapped_column` types. `Base.metadata` is the migration target for Alembic. The existing `RunRow` model in the skeleton is replaced by `Session`, `UploadedFile`, and `Message` models.

```python
# src/db/models.py (structure — not full implementation)
class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    uploaded_files: Mapped[list["UploadedFile"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(back_populates="session", cascade="all, delete-orphan")

class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    filename: Mapped[str]
    temp_path: Mapped[str]
    profile_json: Mapped[str]
    uploaded_at: Mapped[datetime]
    session: Mapped["Session"] = relationship(back_populates="uploaded_files")

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    role: Mapped[str]
    content: Mapped[str]
    chart_json: Mapped[str | None]
    created_at: Mapped[datetime]
    session: Mapped["Session"] = relationship(back_populates="messages")
```

## Temp File Storage

CSV files are stored at `{TEMP_DIR}/{session_id}/{original_filename}` where `TEMP_DIR` defaults to the OS temp directory (configurable via `AGENT_TEMP_DIR` env var). On session deletion (explicit DELETE /sessions/{id} or expiry cleanup), the entire `{TEMP_DIR}/{session_id}/` directory is removed with `shutil.rmtree`. On server startup, any `{TEMP_DIR}/` subdirectories whose session_id is not present in the sessions table are removed as orphan cleanup.

## Data Lifecycle

| Event | Action |
|-------|--------|
| POST /sessions | Insert Session row; create `{TEMP_DIR}/{session_id}/` directory |
| POST /sessions/{id}/files | Save CSV to temp path; run profiler; insert UploadedFile row |
| POST /sessions/{id}/messages | Insert user Message row; run Q&A; insert assistant Message row |
| DELETE /sessions/{id} | Delete Session row (cascades to uploaded_files + messages); rmtree temp dir |
| Server startup | Delete sessions where expires_at < now(); rmtree orphaned temp dirs |

## Sensitive Data

- `uploaded_files.temp_path` — points to uploaded user data on disk. Protected by session-scoped access (session_id in URL) and ephemeral storage.
- `uploaded_files.profile_json` — statistical metadata only, no raw PII. However, column names and sample_values (first 3 non-null values) may expose some user data context. Treated as session-private.
- `messages.content` — may contain the user's questions which could reference data values. Treated as session-private.
- No authentication or encryption at rest in Phase 1 (personal local tool). For multi-user deployment, add encryption at rest and access control.
