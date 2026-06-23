# UI

## UI Type

Web chat interface — single-page application served at `http://localhost:8001/app/`. Two-column layout: a narrow left sidebar for session management and a wide right main panel for the chat + dataset workflow.

## Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  [Senior Data Analyst]                        [Audit Log tab]   │
├──────────────────┬──────────────────────────────────────────────┤
│  SESSION SIDEBAR │  MAIN PANEL                                  │
│                  │  ┌──────────────────────────────────────────┐│
│  + New Session   │  │ DATASET PANEL (top)                      ││
│  ─────────────── │  │  [Upload CSV/XLSX/JSON]  [dataset list]  ││
│  Session 1  ✓   │  └──────────────────────────────────────────┘│
│  Session 2       │  ┌──────────────────────────────────────────┐│
│  Session 3       │  │ CHAT THREAD (scrollable)                 ││
│                  │  │                                          ││
│                  │  │  User: What are the top regions?         ││
│                  │  │  ─────────────────────────────────────── ││
│                  │  │  Assistant:                              ││
│                  │  │  [markdown narrative]                    ││
│                  │  │  [sortable table]                        ││
│                  │  │  [Chart.js chart]                        ││
│                  │  │                                          ││
│                  │  └──────────────────────────────────────────┘│
│                  │  ┌──────────────────────────────────────────┐│
│                  │  │ [Question input]          [Send button]  ││
│                  │  └──────────────────────────────────────────┘│
└──────────────────┴──────────────────────────────────────────────┘
```

---

## Views / Screens

### Screen: Root Page (`/app/`)

**Purpose:** The single working surface. Everything happens here.

**Key elements:**

1. **Header bar** — App name "Senior Data Analyst", right-aligned "Audit Log" tab/button (Phase 1: labelled stub showing placeholder text; Phase 2: opens real audit log panel).

2. **Session Sidebar** (left, ~240px wide)
   - "New Session" button at top — calls `POST /sessions`, selects the new session, stores `session_id` in `localStorage`.
   - List of sessions (newest first) — each shows `name`, `dataset_count`, `message_count`. Active session is highlighted.
   - Phase 1: clicking a session loads it (no rename/delete UI). Phase 2: rename on double-click; delete trash icon.
   - Session list loaded from `GET /sessions` on mount; updated after create.
   - Active `session_id` stored in `localStorage` key `analyst_session_id`; restored on page load.

3. **Dataset Panel** (top of main panel)
   - Drag-and-drop upload zone with dashed border — accepts `.csv`, `.xlsx`, `.json`. Clicking opens file picker.
   - On drop/select: calls `POST /datasets` (multipart); shows upload progress indicator; on success adds dataset chip to the list below.
   - Dataset list below the dropzone: each chip shows `name` (e.g. `sales.csv`), `row_count` formatted (e.g. "1,234 rows"), a "Ready" green badge.
   - If no session is selected, dataset panel shows "Create or select a session to upload data."
   - Upload error: red banner below the dropzone with the error message.

4. **Chat Thread** (scrollable main area)
   - Ordered list of `Message` items (user + assistant turns).
   - User messages: right-aligned grey bubble with question text.
   - Assistant messages: left-aligned white card containing:
     - `RichResponse` component (see below)
   - Auto-scrolls to bottom on new message.
   - Empty state: centered text "Upload a dataset and ask a question to get started."
   - Loaded from `GET /sessions/{session_id}` on session select — messages array.
   - New messages appended from the SSE stream.

5. **Chat Input** (pinned to bottom)
   - Full-width textarea (single line, auto-expanding to 3 lines max).
   - "Ask" button on the right. Disabled when no session, no datasets, or while streaming.
   - Enter key submits (Shift+Enter for newline).
   - Placeholder: "Ask a question about your data…"

---

### Component: `RichResponse`

The rendered output of one assistant turn. Composed of up to three sub-components, rendered in order:

**1. Narrative block**
- Markdown text rendered with basic formatting (bold, italic, lists, code spans). Use a lightweight markdown renderer (e.g. `marked` or `react-markdown`).
- Appears first, before table and chart.
- Streaming: text tokens from `chunk` SSE events are appended in real time as they arrive — the user sees the text grow.

**2. DataTable** (conditional — present when `table` SSE event received)
- Shows `columns` as headers, `rows` as rows.
- Column headers are clickable to sort ascending/descending (client-side sort, no re-query).
- Shows "Showing N of M rows" footer when row_count > rows.length (capped at 500).
- Monospace font for numeric columns; left-align text, right-align numbers.
- Phase 1: copy-to-CSV button (copies visible rows as CSV text to clipboard).

**3. AnalystChart** (conditional — present when `chart` SSE event received)
- Chart.js chart rendered via `react-chartjs-2`.
- Chart types supported: `bar`, `line`, `pie`.
- Chart dimensions: 100% width, fixed 320px height.
- Legend displayed below chart.
- No interactivity beyond Chart.js built-in hover tooltips.
- Chart spec comes from `ChartSpec` in the SSE `chart` event.

**Status indicator while streaming:**
- A pulsing dot / "Thinking…" indicator visible between the question submission and the first `chunk` event.
- Status messages from `status` SSE events shown as small grey italics above the narrative (e.g. "Loading schema…", "Running query…") — replaced by the next status, disappear when `done` arrives.

**SQL attribution (hover):**
- A small "SQL" chip below the chart/table. On hover, shows a `<pre>` tooltip with the SQL string from `RichResponseModel.sql`. Gives the user visibility into what was executed.

---

### Component: `DataTable` (sortable)

| Behaviour | Detail |
|-----------|--------|
| Initial sort | None (preserves query order) |
| Sort trigger | Click column header — cycles: asc → desc → none |
| Max displayed rows | 500 |
| Row overflow label | "Showing 500 of {row_count} rows. Download for full results." (download is a Phase 2 stub labelled "[Coming soon]") |
| Column alignment | Numbers right-aligned; text left-aligned; auto-detected |
| Zebra striping | Alternate row background (#f9fafb) |

---

### Audit Log Panel (Phase 1: stub; Phase 2: real)

**Phase 1 behaviour:** Clicking "Audit Log" in the header opens a right-side drawer or replaces the main panel content with:
```
[Audit Log]
─────────────────────────────────────
This panel will show every SQL query the agent ran,
with dataset name, row count, and latency.

[Coming in Phase 2]
```
The drawer close button works. The stub is labelled so it is not mistaken for a bug.

**Phase 2 behaviour:** Replaces stub with a paginated table of `QueryLog` entries: columns = Timestamp, Dataset, SQL (truncated to 80 chars with "…" and full text on hover), Rows, Latency (ms), Status.

---

## Error States

| Error scenario | UI treatment |
|---------------|--------------|
| Dataset upload fails | Red banner below upload zone: "Upload failed: {error message}. Try again." Disappears on next upload attempt. |
| Chat query fails (SSE `error` event) | The streaming message card shows a red-bordered error box: "Could not answer this question: {message}". Retry by rephrasing. |
| Session create fails | Alert banner at top: "Could not create session. Is the server running?" |
| Server unreachable | All API calls show: "Could not reach the server. Make sure it's running on port 8001." |
| No datasets in session | Chat input shows tooltip on disabled "Ask" button: "Upload at least one dataset first." |
| Empty question | "Ask" button is disabled when input is blank. |

## Loading States

| State | Indicator |
|-------|-----------|
| Session list loading | Skeleton placeholder rows in sidebar |
| Dataset uploading | Spinner on upload zone + progress percentage if file size > 1 MB |
| Query streaming | Pulsing dot + node status messages (see RichResponse above) |
| Ask button during stream | Disabled + "Analysing…" label |

## Session Persistence (browser)

- On mount: read `localStorage.analyst_session_id`. If set, call `GET /sessions/{id}` to verify it exists. If 404, clear `localStorage` and show empty state.
- On session select: write `localStorage.analyst_session_id = session_id`.
- On page refresh: the active session, its datasets, and its message history are fully restored from the API.

## Responsive Behaviour

> **Assumed:** The app is desktop-only (1024px+ width). No mobile breakpoints are required in Phase 1. The sidebar collapses to an icon strip at < 768px but no further responsive work is in scope.

## Frontend Build Notes

- `NODE_OPTIONS=--no-experimental-webstorage` must be set in `package.json` `dev`/`build` scripts (Node ≥25 safety rule from `harness/patterns/tech-stack.md`).
- `postcss.config.mjs` with `{ plugins: { '@tailwindcss/postcss': {} } }` must exist for Tailwind v4 utility generation.
- The built static export is at `frontend/out/` — mounted by FastAPI at `/app`.
- All API calls use relative paths (`/sessions`, `/datasets`, `/chat`, `/audit`) — single-origin, no CORS config needed in production.
