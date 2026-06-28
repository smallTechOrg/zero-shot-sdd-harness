# UI

---

## UI Type

A single-page web dashboard — Next.js 15 static export served at `:8001/app/`, the boilerplate's capability UI slot `frontend/src/app/page.tsx`. One screen in Phase 1; the layout already shows the full vision via labelled stubs.

## Views / Screens

### Screen: Analyst (the one Phase 1 page)

**Purpose:** upload a CSV, ask a question, watch the agent work, read the answer with chart + table + code.

**Layout:** a left sidebar (library/sessions stubs) + a main column (upload → question → live run → answer).

**Key elements (REAL in Phase 1):**
- **UploadPanel** — file picker / drop zone → `POST /datasets`; on success shows filename, row count, and the column list.
- **QuestionBox** — text input + Ask button → `POST /datasets/{id}/runs`; disabled until a dataset is loaded.
- **StepStream** — live area subscribed to `GET /runs/{id}/stream` (SSE): shows the **plan** first, then each **step** ("writing code", "running code"), and any **retry** with its error message, ending in the final result. This is the transparency surface — the user sees the agent reason.
- **AnswerCard** — the plain-English answer.
- **ChartView** — interactive chart rendered with `react-plotly.js` from the run's `chart_spec` (Plotly JSON). Pan/zoom/hover work. If no chart, shows "No chart for this result".
- **TableView** — the summary table from `table_json`.
- **CodeAccordion** — a collapsed "Show code" section revealing the exact pandas that produced the answer.

**Key elements (labelled NON-FUNCTIONAL stubs — must read "Coming soon", never look broken):**
- **LibraryStub** (left sidebar) — "Dataset Library — coming soon", a greyed list placeholder.
- **HistoryStub** — "History — coming soon" panel.
- **FollowUpsStub** — under the answer, a greyed "Suggested follow-ups — coming soon" strip.
- **CostStub** — header badges "Tokens · Cost · Session total · Steps · Timer — coming soon", visibly disabled.

**Actions available:**
- Upload a CSV.
- Type and submit a question.
- Expand/collapse the code.
- Interact with the chart (zoom/hover).

## Error States

- **Upload error** (non-CSV / unparseable): inline red banner with the API message; question box stays disabled.
- **Network error**: "Network error — is the server running?" banner.
- **Run failure** (agent gave up after retries): the StepStream shows the retry attempts + final error, and an AnswerCard-style failure card ("Couldn't answer this after N attempts — see the errors above"). Not a silent failure.
- **Loading**: while a run streams, the Ask button shows a spinner and the StepStream animates per event.
- **Stub clarity**: every stub carries a visible "Coming soon" label and a muted style so it is never mistaken for a bug.

## Tech Stack

Next.js 15 + React 19 + Tailwind, static export (`pnpm build` → `frontend/out/`). Charts via `react-plotly.js` + `plotly.js`. E2E via Playwright (`frontend/tests/e2e/analyst.spec.ts`) driving the live `:8001/app/` app: uploads the sample olist CSV, asks a question, and asserts a real answer + chart + table + code render (not just HTTP 200).
