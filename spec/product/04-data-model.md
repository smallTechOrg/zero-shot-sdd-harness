# Data Model

## Storage Technology

SQLite, accessed via SQLAlchemy ORM. The database file lives at `data/datachat.db` relative to the project root. SQLite is sufficient for a single-user local tool with no concurrent writers. No migrations tool is required in v0.1 — tables are created with `Base.metadata.create_all()` on startup. If the schema changes in a later phase, Alembic will be introduced.

Raw CSV files are stored on disk in the `uploads/` directory, named by a UUID to avoid collisions and to prevent exposing original filenames in file paths.

## Entities

### Entity: Upload

Represents a single CSV file that has been successfully uploaded and parsed.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | String (UUID4) | yes | Primary key; generated server-side at upload time |
| filename | String | yes | Safe on-disk filename, e.g. `3f2a...csv` — the UUID-based name used in `uploads/` |
| original_filename | String | yes | The original filename as supplied by the user (e.g. `sales_q1.csv`) |
| row_count | Integer | yes | Number of data rows in the CSV (excluding the header) |
| columns | JSON (list of strings) | yes | Ordered list of column header names as detected by pandas |
| uploaded_at | DateTime (UTC) | yes | Timestamp when the upload was completed and stored |

### Entity: Query

Represents a single natural-language question asked against an uploaded CSV, along with the Gemini-generated answer.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | String (UUID4) | yes | Primary key; generated server-side |
| upload_id | String (UUID4) FK → Upload.id | yes | The CSV this question was asked about |
| question | Text | yes | The raw natural-language question submitted by the user |
| answer | Text | yes | The plain-text answer returned by Gemini |
| created_at | DateTime (UTC) | yes | Timestamp when the query was completed |

### Relationships

- `Query.upload_id` is a foreign key to `Upload.id` (many queries → one upload)
- Deleting an upload does not cascade-delete queries in v0.1; queries become orphaned but remain in the DB for audit purposes

## Data Lifecycle

- **Uploads** are created when a user posts a valid CSV. They are never updated. There is no delete endpoint in v0.1.
- **Queries** are created when the Gemini answer is received and stored. They are never updated or deleted.
- **CSV files on disk** persist indefinitely in `uploads/`. No TTL or cleanup job exists in v0.1.
- There is no archival or soft-delete mechanism in v0.1.

## Sensitive Data

- The `question` field may contain data the user considers sensitive (e.g., references to revenue figures or PII that appears in the CSV). In v0.1 no special encryption is applied — the database is local and unencrypted.
- The Gemini API key is never stored in the database. It is read from an environment variable (`GEMINI_API_KEY`) at runtime.
- Raw CSV files on disk may contain PII. Users are responsible for the security of their local environment. No access control or file encryption is implemented in v0.1.
