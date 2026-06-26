# UI

## UI Type

Single-page web application (Next.js static export). Two logical panels on one page: an upload panel on the left/top and a chat panel on the right/bottom. No separate routes for Phase 1. Phase 2 adds a `/dashboard` route for pinned charts.

---

## Views / Screens

### Screen: Main Page (`/app/`)

**Purpose:** The single working surface for Phase 1. The user uploads a CSV and then asks natural-language questions about it. The left/top panel handles upload; the right/bottom panel shows the answer thread.

#### Upload Panel (`components/UploadPanel.tsx`) — REAL in Phase 1

**Key elements:**
- File picker: drag-and-drop zone or "Browse" button. Accepts `.csv` only. Shows the selected filename once chosen.
- "Upload" button: enabled only when a file is selected and no upload is in progress.
- Loading state: spinner replaces the button while the upload is in progress.
- Schema preview: after a successful upload, shows the table name (e.g. `sales_data_a3f7b2c1`) and a two-column list of column names + inferred types (e.g. `product_name TEXT`, `revenue REAL`).
- Error state: a red alert box with the error message if upload fails.
- "Join another file" link — **NON-FUNCTIONAL STUB, Phase 3**: grey text link below the schema preview, with a tooltip "Coming in Phase 3 — multi-file joins". Visibly greyed out. Clicking it shows a toast "Coming soon — multi-file join support is planned for a future release."

**Actions:**
- Select file → shows filename
- Click "Upload" → calls `POST /upload` → shows schema on success, error on failure
- Click "Join another file" (stub) → shows "coming soon" toast

#### Chat Panel (`components/ChatPanel.tsx`) — REAL in Phase 1

**Purpose:** Accept a natural-language question and display the full answer (SQL + chart + insight) inline. Multiple questions accumulate as a scrolling thread.

**Key elements:**
- Disabled state: before a CSV is uploaded, the question input and "Ask" button are greyed out with placeholder text "Upload a CSV file first."
- Question input: single-line text field, max 2000 characters.
- "Ask" button: enabled only when a file is uploaded and the input is non-empty.
- Loading state: "Thinking…" spinner appears in the answer thread while the pipeline runs.
- Answer cards: each question/answer pair appears as a card in the thread (newest at bottom). See `AnswerCard` below.

**Actions:**
- Type a question → "Ask" button enables
- Submit question → calls `POST /query` → shows AnswerCard on success

#### Answer Card (`components/AnswerCard.tsx`) — REAL in Phase 1

Each answer card contains three sections, visually separated:

1. **SQL section:** A syntax-highlighted code block (`<pre><code>`) showing the SELECT query that was run. Labelled "SQL Query".
2. **Chart section:** A Recharts chart rendered from `chart_spec`. Chart type is chosen automatically (bar, line, pie, scatter, or empty). Labelled "Chart". For `type: "empty"`: renders a grey box with the `message` text ("Query returned no rows.").
3. **Insight section:** A plain-text paragraph. Labelled "Insight".

At the bottom of each card:
- "Pin to Dashboard" button — **NON-FUNCTIONAL STUB, Phase 2**: grey button with a bookmark icon and tooltip "Coming in Phase 2 — save this chart to your dashboard." Clicking it shows a toast "Coming soon — dashboard pinning is planned for a future release."

#### Dashboard Tab (stub nav link) — **NON-FUNCTIONAL STUB, Phase 2**

A disabled nav link in the header labelled "Dashboard" with a grey colour and a `[Coming in Phase 2]` badge. Clicking it shows a toast "Coming soon — a dashboard for pinned charts is planned for Phase 2."

#### Auth / Sign In (stub nav link) — **NON-FUNCTIONAL STUB, Phase 3**

A disabled "Sign in" link in the header with grey colour and a `[Coming in Phase 3]` badge. Clicking shows "Coming soon — user accounts are planned for a future release."

---

### Screen: `/app/dashboard` — **NON-FUNCTIONAL STUB, Phase 2**

Route does not exist in Phase 1. The Dashboard nav link on the main page shows a coming-soon toast.

When built in Phase 2: shows a grid of pinned `AnswerCard` tiles rendered from stored `chart_spec` JSON (no re-query needed).

---

## Error States

| State | Presentation |
|-------|-------------|
| Upload fails (413 / 422 / 500) | Red alert box below the upload button with the error message from `error.message`. "Try again" link resets the upload panel. |
| Query pipeline fails (`status: "failed"`) | Answer card appears with an amber background and the `error` string. The SQL, chart, and insight sections are omitted. |
| Network error (fetch throws) | Red alert box: "Network error — is the server running? Check that the backend is running at `http://localhost:8001`." |
| Session expired (404 from `/query`) | Alert: "Session not found. Please re-upload your CSV." Upload panel resets. |
| Question too long (client-side) | Input shows character count (e.g. "1998 / 2000"); "Ask" button disables when limit reached. |

---

## Loading / Empty States

| State | Presentation |
|-------|-------------|
| No CSV uploaded yet | Chat panel shows grey placeholder: "Upload a CSV file to get started." Question input and Ask button disabled. |
| Upload in progress | Button replaced by spinner; file picker disabled. |
| Query in progress | "Thinking…" spinner card appears at the bottom of the chat thread; question input disabled until response arrives. |
| Empty chart result | Grey chart area with text "Query returned no rows for this question." |

---

## Stub Labelling Convention

Every stub element must be **visibly non-functional** to a first-time user:

- Rendered in grey (`text-gray-400`, `bg-gray-100`, `opacity-50`)
- Has a tooltip or badge: `"Coming in Phase N"` or `"Coming soon"`
- Clicking triggers a toast notification (not a navigation or API call)
- Never hidden — the user should see the vision, not be confused by missing features

The `StubBadge` component (`components/StubBadge.tsx`) renders a small grey pill next to stub elements.

---

## Frontend Tech Stack

> HOW lives in `spec/architecture.md § Stack`. This section restates only the UI-specific choices.

- Next.js 15.3.0, `output: 'export'`, `basePath: '/app'`
- React 19, TypeScript
- Tailwind v4 (requires `frontend/postcss.config.mjs`)
- Recharts `^2.x` for chart rendering
- `NODE_OPTIONS=--no-experimental-webstorage` in all npm scripts for Node ≥25 compatibility
- Single-origin run path: `cd frontend && pnpm build` → `uv run python -m src` → `http://localhost:8001/app/`
