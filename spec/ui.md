# UI

> Single-screen web app served at `http://localhost:8001/app/`. Next.js 15 static export. The Phase-1 screen delivers the full primary journey (upload → profile → ask → answer + chart + table + show-its-work) and shows ALL later features as clearly-labelled non-functional stubs.

---

## UI Type

Web app (single page, local). Built from the skeleton's `frontend/`, replacing the transform form in `frontend/src/app/page.tsx`.

## Views / Screens

### Screen: Analyst (the single Phase-1 screen)

**Purpose:** Upload a dataset, see its profile, ask a question, and read the answer with its chart, table, and reasoning.

**Layout:**
- **Left sidebar — Datasets (STUB in Phase 1):** shows the current dataset only; a greyed list with a "Past datasets — coming soon" label. (Real in Phase 2.)
- **Main column:**
  - **Uploader (REAL):** drag/drop or pick a `.csv`. Beside it: a greyed "Excel (.xlsx) — coming soon" note (STUB, Phase 5).
  - **Profile card (REAL):** appears after upload — row count, a table of columns (name + inferred type), and a health summary (nulls / distincts / numeric ranges).
  - **Ask box (REAL):** a text input + "Ask" button for ONE question. Below it: a greyed "Suggested questions" chip row (STUB, Phase 6) and a disabled "Ask a follow-up" affordance labelled "coming soon" (STUB, Phase 3).
  - **Answer panel (REAL):** plain-English answer with key numbers emphasized; ONE auto-picked chart (bar/line/pie via Recharts, or table-only); a compact summary table.
  - **Show its work (REAL, collapsible):** the plan, the step trace (each step ok/failed with any recovered SQL error shown), and the exact DuckDB SQL that ran. Per-question cost shown here (REAL).
  - **Compare another file (STUB, Phase 4):** a greyed button labelled "coming soon".
  - **Column notes (STUB, Phase 5):** a greyed panel labelled "coming soon".
  - **Daily cost (STUB, Phase 6):** a small figure showing "—" with a "coming soon" tooltip. (Per-question cost is real; the daily roll-up is the stub.)

**Actions available:**
- Upload a CSV → see the profile.
- Type a question → Ask → see the answer + chart + table + trace.
- Expand/collapse "Show its work".

## Error States

- **Upload loading:** spinner + "Profiling your data…"; on failure a clear inline message (e.g. "Couldn't read that CSV — check it's a valid file"). A stub must never look like this error — stubs are visibly greyed/labelled, errors are red.
- **Ask loading:** live "working" indicator that updates as the agent progresses (planning → running SQL → writing answer), so the ~30s feels responsive.
- **Ask failure:** the answer panel shows the failure message AND the "show its work" trace stays available (so the user sees what was tried, incl. a SQL error that couldn't be corrected after retries).
- **Network error:** "Network error — is the server running?" (matches the skeleton's pattern).

## Tech Stack

Next.js 15 + React 19 + Tailwind v4 (skeleton), static export served by FastAPI at `/app/`. Charts via **Recharts** (added to `frontend/package.json`). E2E via **Playwright** (`frontend/tests/e2e/`).
