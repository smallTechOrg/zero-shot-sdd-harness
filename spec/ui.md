# UI

A single-page, chat-style web app (Next.js static export, served at
`http://localhost:8001/app/`). Phase 1 delivers a real, working path plus clearly-labelled
non-functional stubs so the user sees the full vision without mistaking a stub for a bug.

## Layout

- **Left sidebar** — dataset + navigation. Top: the active dataset name. Below: labelled
  STUB sections (see Stubs), each greyed with a "Coming soon" badge.
- **Main column** — the chat transcript and composer.
- **Right/inline profile panel** — the auto-profile of the uploaded dataset.

## Primary Path (REAL in Phase 1)

1. **Upload** — a drop zone / file picker. On upload, calls `POST /api/datasets`, shows a
   loading state, then renders the profile panel.
2. **Profile panel (REAL)** — table of columns: name, dtype, range (min/max or top values),
   missing-value count, distinct count; plus row/column totals and file size.
3. **Ask (REAL)** — a chat composer. Sending calls `POST /api/analyses`. While running, shows
   live step status (planning → generating code → executing → verifying) and an elapsed timer.
4. **Answer bubble (REAL)** — prose answer + key numbers, ONE interactive chart (rendered from
   `chart_spec`), and a collapsible "Code it ran" block showing the exact pandas code.
   On a failed run, shows the clear "here's what I tried" message instead.

## Stubs (NON-FUNCTIONAL, clearly labelled "Coming soon")

Each is visible, greyed, and tagged so it is never mistaken for a bug:

- Multi-file upload / dataset switcher / join-compare
- Folder-as-one-source
- Saved sessions & cross-day history
- Column annotations editor
- Derived-dataset library
- Follow-up question suggestions (chips under each answer)
- Tokens + estimated cost per query and running daily total
- External SQL-database source
- Excel (`.xlsx`) upload

## Transparency (first-class, REAL)

- Every answer exposes the exact code (collapsible) and the agent's step status.
- Live status + elapsed timer while the loop runs.

## States

- Empty (no dataset) → prompt to upload.
- Uploading / profiling → spinner.
- Ready → profile shown, composer enabled.
- Running query → step status + timer.
- Answered → answer bubble with chart + code.
- Failed query → "what I tried" message, composer re-enabled.

## E2E (Playwright, `frontend/tests/e2e/`)

Smoke test of the primary journey against the live app at `http://localhost:8001/app/`: page
loads and is styled, upload a fixture CSV, profile renders, ask a question, a real answer bubble
with a chart and the code block appears (not a spinner or error). Required for the Phase 1 gate.
