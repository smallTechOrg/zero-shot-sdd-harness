# UI

## UI Type

Local browser web dashboard — a single-page application served as a Next.js static export from `http://localhost:8001/app/`. No login screen; no multi-page routing in Phase 1. The single page contains the full analysis workflow.

---

## Views / Screens

### Screen: Analysis Dashboard (Phase 1 — the only screen)

**Purpose:** The user uploads a CSV file, asks a question, and sees the plain-English answer plus an interactive chart. Everything happens on one page.

**Layout:** Two-column on wide screens (upload/input panel on left, results on right); single-column stacked on narrow screens.

**Key elements:**

**Left panel — Input:**
- **CSV Upload Zone:** A drag-and-drop area with a "Browse files" fallback. Accepts `.csv` files only. On successful upload, the zone collapses and shows: filename, row count, and the first few column names. An "Upload a different file" link re-opens the upload zone. Calls `POST /datasets` on file selection (no separate "Upload" button — triggers on file selection/drop).
- **Question Input:** A textarea (`placeholder="Ask a question about your data…"`) that activates after a dataset is loaded. Disabled with a tooltip "Upload a CSV first" when no dataset is loaded.
- **Analyze Button:** Disabled until both a dataset is loaded and the question textarea is non-empty. Shows spinner + "Analyzing…" during the `POST /analyses` call.
- **"Connect Database" button (LABELLED STUB):** Visually present in the left panel with the text "Connect a Database" and a clearly visible badge: "**Coming in Phase 2**". The button is disabled (`cursor: not-allowed`, 50% opacity). Clicking it shows a tooltip: "SQL database connectivity is coming in Phase 2." This is never mistaken for a bug.

**Right panel — Results:**
- Initially shows a placeholder: "Your analysis will appear here."
- After a successful analysis:
  - **Answer card:** Heading "Answer", body = plain-English `answer_text` in a clean card.
  - **Chart area:** Plotly chart rendered with `Plotly.react()`. If `chart_json` is null, the chart area is hidden.
  - **Metadata footer:** "Asked: [question]" and "Dataset: [filename]" in small grey text.
- On error (`status === "failed"`): shows an error card with the `error` field and a "Try again" prompt.

**Loading state:** While `POST /analyses` is in progress, the right panel shows a centered spinner with the text "Analyzing your data with Gemini…".

---

### Screen: Error State

**Purpose:** Surface agent pipeline errors to the user without a crash.

**Key elements:**
- Red error card with icon, heading "Analysis failed", and the `error` field from the API response.
- "Try again" button that resets the question input and clears the error (does not require re-uploading the CSV).

---

## Error States

| Situation | UI Response |
|---|---|
| File too large (>50 MB) | Toast notification: "File too large — please upload a file under 50 MB." |
| File not a valid CSV | Toast notification: "Could not parse file as CSV — please check the format." |
| Empty question submitted | Analyze button remains disabled; no network call |
| Agent pipeline failure | Error card in results panel with the error message; "Try again" button |
| Network error (server not running) | Error card: "Could not reach the server — is it running at localhost:8001?" |
| Plotly chart JSON invalid | Chart area hidden silently; text answer still shown |

---

## Tech Stack

Next.js 15 + React 19 + TypeScript, statically exported (`output: 'export'`, `basePath: '/app'`), served by FastAPI at `/app`. Tailwind CSS v4 (PostCSS plugin via `@tailwindcss/postcss` in `postcss.config.mjs`). Plotly.js via `plotly.js-dist-min` npm package (lightweight Plotly bundle). `pnpm` for package management. `NODE_OPTIONS=--no-experimental-webstorage` set in build/dev scripts to prevent Node ≥25 `localStorage` crash.

**Build path:** `cd frontend && pnpm build` → generates `frontend/out/` → FastAPI mounts at `/app`.
**Test path:** Single server at `http://localhost:8001/app/` (not `localhost:3000`).
