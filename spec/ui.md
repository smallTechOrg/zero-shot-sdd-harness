# UI

The single-page web app served at `http://localhost:8001/app/`. Replaces the skeleton's transform form in `frontend/src/app/page.tsx`. Visually complete in Phase 1: real UI for the one working path plus clearly-labelled non-functional stubs for everything later.

---

## UI Type

Web app (Next.js 15 static export + React 19 + Tailwind v4). Chat-style question/answer over an uploaded dataset. Charts render client-side with `vega-embed`.

## Views / Screens

Single page, three regions: a left **sidebar** (mostly stubs in Phase 1), a top **profile/context bar**, and the main **chat + answer** column.

### Screen: Empty State  *(Phase 1 — REAL)*

**Purpose:** the clean first-run state — just get a file in.

**Key elements:**
- A single, prominent **upload box** (drag-drop or click; accepts `.csv`, `.xlsx`).
- No bundled sample data, no guided tour.
- The sidebar and toolbar are visible but greyed with **"Coming soon"** labels (see Stubs).

**Actions:** upload a file → `POST /datasets`.

### Screen: Profile Card  *(Phase 1 — REAL)*

**Purpose:** confirm the agent understood the data before asking.

**Key elements:**
- Dataset name + exact **row count** + column count.
- A table of columns: name, inferred **type**, null count / **quality flag** (e.g. "12% nulls").
- A few sample rows.

**Actions:** proceed to ask a question (the chat input activates once a dataset is loaded).

### Screen: Ask & Answer  *(Phase 1 — REAL)*

**Purpose:** ask a plain-language question and get a verifiable answer.

**Key elements:**
- A **question input** at the bottom (chat-style).
- While running: a single **"Analyzing…"** spinner (Phase 1 — the multi-step live progress is a labelled stub).
- The **answer block**: plain-language answer with key numbers (prominent), a short **narrative** paragraph, at least one **rendered chart** (Vega-Lite via `vega-embed`), a **summary table**, and a collapsible **"Show code"** panel with the exact pandas.
- On failure: the error message from the run is shown in-place (never a silent blank).

**Actions:** submit a question → `POST /runs`; expand/collapse the code panel.

## Stubs (Phase 1 — clearly labelled NON-FUNCTIONAL, become real in Phase 2)

Each is visibly disabled with a "Coming soon" / "Phase 2" tag so it never reads as a bug:
- **Library / Projects** sidebar — list of datasets, grouping, rename, column annotations.
- **History** panel — past questions, revisit, re-run.
- **Cost meter** — tokens + estimated $ per question and running total; expensive-run warning.
- **Live step progress** — "Planning… / Running code… / Retrying… / Writing answer…" (Phase 1 shows a single spinner instead).
- **Multi-dataset selector** — choosing/auto-detecting multiple active datasets, cross-file joins.
- **Follow-up suggestions** — 2–3 suggested next questions after an answer.

Phase 2 wires History, Cost meter, live progress, and conversation memory (follow-ups that build on prior turns) into real features. Library/Projects/rename/annotations and multi-dataset remain deferred beyond this build.

## Error States

- **Upload error** (bad format / too large / unparseable): inline message on the upload box with the `error.message` from the API.
- **Analysis failure** (agent failed after retries / LLM error): the answer block shows the run's `error` text and a note that the code/steps couldn't complete — with any generated code still shown if present.
- **Network error** (server down): inline "Network error — is the server running?" (matches skeleton behaviour).
- **Loading:** upload spinner on the box; "Analyzing…" spinner on the answer area.

## Tech Stack

Next.js 15 static export (`output: 'export'`, `basePath: '/app'`, `trailingSlash: true`), React 19, Tailwind v4 (via `@tailwindcss/postcss`). Charts: `vega`, `vega-lite`, `vega-embed` (added to `frontend/package.json`). Fetch calls go to the same origin (`/datasets`, `/runs`). Components live under `frontend/src/app/components/` (e.g. `UploadBox`, `ProfileCard`, `ChatInput`, `AnswerBlock`, `ChartView`, `CodePanel`, and stub components `LibrarySidebar`, `HistoryPanel`, `CostMeter`, `ProgressSteps`).
