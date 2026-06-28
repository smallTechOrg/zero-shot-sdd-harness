# UI

## UI Type

Web app — Next.js 15 static export (`output: 'export'`), served at `http://localhost:8001/app/`. A single conversational workspace: upload + profile panel on one side, chat/analysis on the other.

## Views / Screens

### Screen: Workspace (single page)

**Purpose:** Upload data, ask questions, read streamed answers, inspect the code that ran.

**Key elements:**
- **Upload zone** (real, Phase 1) — drag/drop or pick a CSV; shows progress.
- **Profile panel** (real, Phase 1) — table of columns: name, dtype, missing %, min/max/mean, distinct.
- **Chat / ask box** (real, Phase 1) — type a question, submit.
- **Streamed answer** (real, Phase 1) — live step badges ("Planning…", "Running analysis…"), then streamed plain-language answer with key numbers.
- **Show code** (real, Phase 1) — collapsible block showing the exact pandas that ran locally, with a "rows stayed local" privacy note.
- **Chart panel** (STUB Phase 1 → real Phase 2) — greyed "Coming soon".
- **Summary table** (STUB Phase 1 → real Phase 2) — greyed "Coming soon".
- **Follow-up chips** (STUB Phase 1 → real Phase 2) — greyed "Suggested follow-ups — coming soon".
- **Cost / token meter + daily total** (STUB Phase 1 → real Phase 2) — greyed badge.
- **File library sidebar + compare** (STUB Phase 1 → real Phase 3) — greyed list with "Coming soon".
- **Excel sheet selector** (STUB Phase 1 → real Phase 3).
- **Audit-trail browser** (STUB Phase 1 → real Phase 3).
- **Clarify / plan-confirm prompt** (STUB Phase 1 → real Phase 3).

All stubs are visibly labelled "Coming soon" and styled distinct from live controls so a stub is never mistaken for a bug.

**Actions available (Phase 1):** upload file, view profile, ask question, watch stream, toggle code view.

## Error States

- Upload failure: inline error (unsupported type, too large, parse error).
- Query failure: the stream's `error` event renders a red inline message; partial steps remain visible.
- Network/server down: "Network error — is the server running?" banner.
- Loading: step badges during streaming; skeleton on profile load.

## Tech Stack

Next.js 15 + React 19 + Tailwind, static export. SSE consumed via `fetch` + `ReadableStream`. Vega-Lite (`vega-embed`) for charts in Phase 2. E2E via Playwright in `frontend/tests/e2e/`.
