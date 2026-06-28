# UI

---

## UI Type

Web app — chat-style data-analysis workspace. Next.js 15 + React 19 static export served at `/app/` on the FastAPI origin. Replaces the skeleton's transform form in `frontend/src/app/page.tsx`.

## Views / Screens

### Screen: Workspace (single page)  *(Phase 1 real)*

**Purpose:** upload a CSV, ask questions, see direct answers with code, chart, table, and cost.

**Key elements:**
- **Upload zone** — drag/drop or pick a CSV; on upload shows the auto-profile (columns, types, ranges, row count).
- **Chat thread** — user questions and agent answers in turn order; follow-up turns carry context.
- **Answer card** per turn:
  - Direct answer with key numbers (top).
  - **Live step status** while running (plan → generate code → execute locally → visualize) via SSE.
  - **Collapsible "Show code"** — the exact pandas/DuckDB code that ran.
  - **Collapsible "Show plan"** — the step-by-step reasoning.
  - **Interactive chart** (Recharts: zoom/hover) chosen automatically; or a summary table.
  - **2-3 follow-up suggestion chips** (clickable to ask).
  - **Per-turn token + estimated cost.**
- **Assumptions banner** when the agent best-guessed.

**Actions available:** upload CSV; ask a question; click a follow-up chip; expand code/plan.

### Stubs (Phase 1, clearly labelled NON-FUNCTIONAL)

- **Dataset Library sidebar** — labelled "Coming soon" with a few greyed placeholder entries (real in Phase 2).
- **Running daily cost total** in the header — shows the live per-turn cost summed for the session, labelled "session total — full daily history coming soon" (full multi-day persistence in Phase 2).
- **"Compare datasets" / "Save cleaned dataset" / "Upload Excel"** buttons — visible but disabled with a "Coming soon" tag (later phase).

> Every stub carries a visible "Coming soon" label so it is never mistaken for a bug.

## Error States

- Upload error → inline red banner on the upload zone with the reason.
- Ask failure → the answer card shows the error and (when available) what the agent tried; the turn is still recorded.
- Network/server down → "is the server running?" banner.
- Loading → live step-status indicators per node; chart/table area shows a skeleton.

## Tech Stack

Next.js 15 + React 19 + Tailwind + Recharts. Built with `cd frontend && pnpm build`, served at `:8001/app/`.
