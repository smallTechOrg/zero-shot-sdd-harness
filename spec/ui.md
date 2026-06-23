# UI

Single-page Next.js static-export app, served by FastAPI at `http://localhost:8001/app/`. Same-origin fetches to `/datasets`, `/queries`, `/audit`. Tailwind for styling (requires `frontend/postcss.config.mjs`). Entry: `frontend/src/app/page.tsx` (replaces the transform form).

> All data on the tested path is REAL. Deferred-vision surfaces are present but clearly LABELLED "Coming soon" and non-interactive, so the user sees the direction without mistaking a stub for a bug.

---

## Layout

A two-region layout:
- **Main column (left/center):** dataset upload + status, the ask box, and the answer (text + table).
- **Side panel (right):** the Audit panel.
- **Top:** app title + a tab/nav row with the labelled stub tabs.

---

## Screens / Sections (Phase 1 — REAL)

### 1. Dataset upload + status

- A file picker / drop zone accepting a single `.csv`. On submit → `POST /datasets` (multipart).
- On success: a card showing dataset name, table name, row count, and the detected columns (name + type).
- On load: calls `GET /datasets`; if a dataset exists, shows the most-recent one as the active dataset (session restore). If none, shows an empty-state prompt to upload.
- Errors (`BAD_CSV`, `EMPTY_FILE`) render an inline message, not a crash.

### 2. Ask box

- A text input + "Ask" button, enabled only when a dataset is active.
- On submit → `POST /queries` with `{dataset_id, question}`. Shows a loading state while the graph runs.
- Disabled with a hint when no dataset is loaded.

### 3. Answer

- Renders the latest query result: the formatted `answer_text` (preserve line breaks / basic formatting) ABOVE a data table built from `result_columns` + `result_rows`.
- Shows the `generated_sql` in a collapsible "Show SQL" disclosure.
- On `status:"failed"`, shows the `error` message in an error card (no fake/placeholder table).

### 4. Query history (session restore)

- On load, `GET /queries?dataset_id=…` populates a scrollable history of past questions + answers for the active dataset. Clicking one re-displays its answer + table. Survives reload (re-fetched, not client-only state).

### 5. Audit panel

- On load and after each operation, `GET /audit` populates a list (newest first): operation badge (`ingest`/`query`), timestamp, row count, duration, success/error, and the exact `sql_text` (monospace, expandable). This is the auditable record of every data operation.

---

## Labelled stubs (Phase 1 — NON-FUNCTIONAL, "Coming soon")

Each is visible but visibly disabled/badged so it is never mistaken for a bug:

- **Multi-dataset manager / dataset switcher** — a sidebar list area labelled "Manage multiple datasets — Coming soon" (Phase 2).
- **Charts toggle** — a "Chart view" control on the answer, disabled, badged "Coming soon" (Phase 3).
- **Dashboards tab** — a top-nav tab "Dashboards — Coming soon", non-interactive (Phase 4).
- **Senior-analyst mode toggle** — a switch labelled "Senior analyst mode — Coming soon", disabled (Phase 5).

---

## States

| State | UI |
|-------|-----|
| No dataset | Empty state: "Upload a CSV to begin." Ask box disabled. |
| Dataset loaded | Dataset card + enabled ask box + history + audit. |
| Query running | Spinner / disabled ask button. |
| Query success | Answer text + table + collapsible SQL; new audit entry. |
| Query failed | Error card with message; failed audit entry visible. |
| Reloaded | Active dataset + full history + audit restored from the backend. |

## Styling / build notes

- Tailwind v4 — `frontend/postcss.config.mjs` with `{ plugins: { '@tailwindcss/postcss': {} } }` is mandatory (else unstyled build).
- `output:'export'`, `basePath:'/app'`, `trailingSlash:true` retained. Build with `pnpm build` → `frontend/out/`.
- Node-version safety: keep `NODE_OPTIONS=--no-experimental-webstorage` in the frontend scripts (or pin Node LTS).
