# UI

> Built in the existing Next.js `frontend/` (React 19 / TSX), single-origin, served at `/app` on port 8001. Replaces the skeleton's transform form in `frontend/src/app/page.tsx`. Same information architecture and UX as the source design (Analyse + Database tabs). All API calls go through `frontend/src/lib/api.ts` to the root REST routes. **Phase-by-phase:** Phase 1 ships every surface as a clearly-labelled NON-FUNCTIONAL stub; Phase 2 makes upload + Tables + conversation real; Phase 3 makes sessions/clarification/suggestions real; Phase 4 makes charts + the Database tab real.

---

## UI Type

Web dashboard (single-page, two tabs), served single-origin by FastAPI.

## Tech Stack

Next.js 15 + React 19 + TypeScript (existing `frontend/`), static-exported to `frontend/out/` and mounted at `/app` (UI at `http://localhost:8001/app/`; the `agent.py --run` launcher builds it). Plotly.js (or `react-plotly.js`) for inline charts (Phase 4). SVG for the ER diagram.

## Shell & Global Chrome

- **Header:** app name + tagline; a **Project notes** button opens the global-memory modal (memory/C29); a **yellow stub-mode banner** is shown when `GET /health` reports `provider == "stub"` (so demo output is never mistaken for real output).
- **Layout:** two-panel responsive shell; ≤960px stacks panels, ≤640px stacks cards.
- **Tabs:** `[Analyse]` (default) and `[Database]`.

## Views / Screens

### Screen: Analyse tab

**Purpose:** upload data, ask questions, read answers, manage sessions.

**Key elements:**
- **Sidebar — Sessions panel** (C9): list with name / first-question, turn count, relative time; checkbox bulk-select; click to resume; inline rename; **+New**; **Delete selected**; **Clear all** (modal). Data from `GET /sessions`; mutations via `PATCH /sessions/{id}/name`, `DELETE /sessions/{id}`, `DELETE /sessions`.
- **Sidebar — Token usage widget** (C18): model name; Last query In/Out/Cost and Today In/Out/Queries/Cost from `GET /stats/daily`; storage row = dataset count + total rows; client-side pricing table ("N/A" unknown). Plus the **C29 token-budget bar at rest**.
- **Datasets card — "Tables":** filter tabs All | Uploaded | Derived | This session; per row checkbox + filename + rows×cols + "cols" toggle + **clean** (uploaded only) + **delete**; Derived/Stale badges; **Re-derive** on stale rows; inline delete-confirm mentioning N derived children; re-fetch `GET /datasets` after each completed query to surface new derived sets (C25).
- **Upload card** (C1, C11, C13, C16, C17): drag-drop files AND folders (reads `_notes`/`context`/`readme` as folder notes, `<stem>.notes.txt` per file); **Choose files**; staged file map (rename, typed notes, attach notes file, remove); **Upload N file(s)** ≤3 concurrent with per-file states; **409 → "Use existing / Upload anyway"** inline resolver (`force=true`). Calls `POST /upload`.
- **Conversation card** (C2, C3, C6, C7, C22, C23, C32): thread (`role="log"`, `aria-live="polite"`); per turn = question (blue) + timestamp/elapsed, optional **Best effort** badge (`is_best_effort`), rendered Markdown answer (`answer_html`), iteration + token counts, **Datasets used** disclosure, **Steps inspector** (collapsible; per-step dark code block + result/error + Copy; red **Error** badge), 2–3 follow-up **suggestion chips** (`suggested_questions`), **Export MD**; **clarification turns** amber with "Needs clarification" → re-submit `skip_clarification:true` (C26); **C32** per-turn collapse/expand + Collapse all / Expand all (`sessionStorage`). Input: question textarea (Enter submit, Shift+Enter newline), **Ask** (spinner/disabled while running), **Stop** (AbortController), Progress row (elapsed timer + Step N/M bar from `GET /runs/current`; "Checking…" during C26). Calls `POST /ask`.

**Actions available:** upload, ask, stop, resume/rename/new/delete sessions, edit memory, export answer, re-submit clarification, click suggestion chips.

### Screen: Database tab (session-scoped data universe)

**Purpose:** explore the data universe, schema, lineage, and per-dataset details.

**Key elements:**
- **Header:** session name + "N uploaded / M derived" + **Clear database** (danger → `DELETE /datasets`).
- **Schema panel — full ER diagram** in SVG (`#lineage-svg`) via `renderERDiagram(datasets)`: each dataset is a table card listing columns (first 8 + "+N more", zebra rows, dtype color dot: number=blue, text=purple, date=amber, boolean=green, other=grey); uploaded = blue header, derived = green header + "derived" tag. Inferred FK crow's-foot edges via **`_erFkLinks(datasets)`** — the single source of truth for both edges and the right-panel PK/FK badges: links columns ending `_id` shared by ≥2 tables, a `zip_code_prefix` family normalized to a geolocation hub, exact-name shared specific columns, with a denylist of generic columns; canonical PK table chosen by filename. Edges = column-anchored orthogonal elbows routed around cards (dodgeX), crow's-foot at the many/FK end, tick at the one/PK end; derived edges dashed green; hover-only join-key pill. Force-directed layout + overlap resolution + aspect-aware x-stretch + auto-fit; controls **Fit/+/−**, drag-pan, wheel-zoom (0.5×–3×); click card → `selectDataset(id)`; hover highlights its relationships and dims others to ~0.3.
- **Table Description panel:** filename + origin/stale badges; "rows × cols / FORMAT"; derived block (parent chips + collapsible derivation code); **Keys** block (PK/FK from `_erFkLinks`); columns table (Name | Type with PK/FK badges); Context notes textarea auto-saving via `PATCH /datasets/{id}/context` + **Generate notes** (C30 poll on `auto_notes_status`); data preview (~10 rows via `GET /datasets/{id}/preview`); actions **Clean / Re-derive / Delete**.
- **Dataset strip:** horizontal chips (uploaded / derived + stale), uploaded first; click = `selectDataset`.

**Actions available:** select dataset, pan/zoom/fit the diagram, edit/generate notes, clean, re-derive, delete, clear database.

## Modals

All `.modal-overlay`, backdrop + Escape close, focus first element: `memory-modal`, `clean-modal`, `clear-sessions-modal`, `del-sel-sessions-modal`, `clear-all-datasets-modal`, `del-sel-modal`, `clear-db-modal`.

## Error States

- **Network / 5xx:** inline error banner in the relevant card ("is the server running?" for network failures); the conversation answer area shows the error, never a blank turn.
- **409 duplicate upload:** inline "Use existing / Upload anyway" resolver.
- **Loading:** Ask button shows a spinner and disables; the progress row shows elapsed time + Step N/M; "Checking…" during the clarification pre-flight.
- **Failed run:** the turn renders the run's `error_message`; a force-finalized run shows the **Best effort** badge instead of an error.
- **Stub mode:** the persistent yellow banner signals that answers are canned, not real.

## Accessibility

`role="log"` + `aria-live` on the thread; `role="list"`/`listitem`; `aria-label` on icon buttons; `aria-modal` + `aria-labelledby` on modals; `role="progressbar"` + `aria-valuenow` on the progress bar; a hidden `#aria-live` region + `announce()` helper; `type="button"` on every non-submit button.

## Phase Mapping (real vs labelled stub)

| Surface | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|---------|---------|---------|---------|---------|
| Two-tab shell + header + stub banner | stub shell (real banner ok) | real | real | real |
| Upload card | labelled stub | **real** | real | real |
| Tables/datasets card | labelled stub | **real** (list + delete) | real | real (+derived/stale) |
| Conversation ask/answer/steps/tokens | labelled stub | **real** (single dataset) | real (multi-turn) | real (+charts) |
| Sessions sidebar | labelled stub | labelled stub | **real** | real |
| Clarification + suggestions | labelled stub | labelled stub | **real** | real |
| Token widget + C29 budget bar | labelled stub | partial (last/today) | real | real |
| Inline charts | labelled stub | labelled stub | labelled stub | **real** |
| Database tab (ER diagram, description) | labelled stub | labelled stub | labelled stub | **real** |
| Clean / Re-derive / Generate notes | labelled stub | labelled stub | labelled stub | **real** |

A labelled stub renders the intended layout with a visible "coming in a later phase" tag so it is never mistaken for a bug.
