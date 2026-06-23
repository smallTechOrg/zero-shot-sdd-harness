# UI

## UI Type

Web single-page app — Next.js 15 + React 19, static export served at `/app`. Replaces the skeleton `transform_text` form in `frontend/src/app/page.tsx`. Same-origin calls to the FastAPI JSON API.

## Views / Screens

### Screen: Analyst Workspace (single page)

**Purpose:** Upload a CSV, ask questions, read the answer + result rows. See the product vision via labelled stubs.

**Key elements:**
- **Upload panel (REAL):** file picker + "Upload" button → `POST /datasets`. On success shows table name, row count, and the column list.
- **Question box (REAL):** text input + "Ask" button → `POST /sessions/{id}/ask`. Disabled until a dataset is uploaded.
- **Answer panel (REAL):** renders `answer_text` (prose) and, collapsibly, the `sql_text` used.
- **Results table (REAL):** renders `result.columns` + `result.rows`.
- **Q&A history (REAL):** lists prior turns for the session (loaded via `GET /sessions/{id}` on load, so it survives restart).
- **Charts panel (STUB):** labelled "Charts — coming soon (not functional)".
- **Multiple datasets panel (STUB):** labelled "Multiple datasets — coming soon (not functional)".
- **Dashboards panel (STUB):** labelled "Dashboards — coming soon (not functional)".
- **Audit log panel (STUB):** labelled "Audit log viewer — coming soon (not functional)".

**Actions available:**
- Upload a CSV/Excel file.
- Ask a question.
- Toggle the SQL view for an answer.

**Persistence:** The current `session_id` is held in the browser (e.g. localStorage) so a reload re-fetches `GET /sessions/{id}` and shows prior turns.

## Error States

- Upload failure (400/500): inline error under the upload panel ("Couldn't read that file — check it's a valid CSV").
- Ask failure (status="failed" or non-200): inline error under the answer panel showing the returned message (e.g. "That query was blocked — read-only only" or an LLM error). The question box stays usable for a retry.
- Loading: spinners/disabled buttons during upload and ask.

## Tech Stack

Next.js 15 + React 19, static export (`output: 'export'` → `frontend/out/`), Tailwind v4 (PostCSS). Charts in Phase 2 use `recharts`. Build with `cd frontend && pnpm build`.
