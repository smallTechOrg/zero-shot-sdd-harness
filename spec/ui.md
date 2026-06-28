# UI — Pandora

A single-page web app (Next.js static export) served at `http://localhost:8001/app/`. One screen, top-to-bottom flow: upload → profile → ask → answer. Built with React 19 + Tailwind v4; charts via `recharts`; LLM markdown via `react-markdown` + `remark-gfm`. Replaces the skeleton's `transform` form in `frontend/src/app/page.tsx`.

## Layout (top to bottom)

1. **Header** — "Pandora — private CSV analysis" + a one-line trust statement ("Your data stays on this machine. Only schema + results reach the model."). Daily cost badge top-right: "Today: $0.00".

2. **Upload zone** (empty state until a file is loaded) — drag/drop or pick a `.csv`/`.xlsx`. Empty-state copy explains the one action. Loading state: "Profiling <filename>…" with a spinner. Error state: human message on parse failure.

3. **Profile card** (after upload) — filename, row × column counts; a per-column table (name, type, missing %, range/distinct); data-quality flags as badges; and 2–3 **suggested-question chips** (click to populate the ask box). This is real and on the tested path.

4. **Ask box** — a text input + "Ask" button. While running, shows the **live step list** ("Generating code → Running code → Summarising"), a step counter, and an elapsed timer driven by the SSE `step` events. Feedback within 100ms (button disables, steps appear).

5. **Answer block** (after the SSE `answer` event):
   - **Plain-language answer** — markdown-rendered (never raw `**bold**`).
   - **Interactive chart** — recharts, driven by `chart_spec`.
   - **Summary table** — the computed result (≤ 200 rows).
   - **Collapsible "Show code & steps"** — the exact runnable pandas (monospace, formatted, with a Copy button) + the steps taken.
   - **Cost line** — "This question: N tokens · ~$0.000X · Today: $0.00YZ".
   - **Stuck state** — if `status:"stuck"`, show the human "here's what I tried" message + the attempted code, not a stack trace.

## Labelled stubs (real on the page, visibly non-functional in Phase 1)
Each is rendered with a muted style and a phase badge so it is never mistaken for a bug:
- **History panel** (collapsed, greyed) — "Run history — coming in Phase 2".
- **Ask-a-follow-up** affordance under the answer — disabled, "Conversation memory — Phase 2".
- **Add another file / join datasets** button — disabled, "Multi-file — Phase 3".
- **Deep analysis (plan & iterate)** toggle next to Ask — disabled, "Phase 4".

## The four states (every view)
- **Empty:** upload zone explains what to do; below it, a greyed "Results will appear here once you ask a question."
- **Loading:** profiling spinner; ask-in-progress step list with context (never a frozen screen).
- **Error:** parse error on upload; "stuck" message on a question — both human, both actionable.
- **Ideal:** profile card + full answer block as above.

## Quality bar (per `harness/patterns/ui-ux.md`)
- One primary action per state (upload, then ask). Keyboard reachable; visible focus rings; semantic `<button>`/`<label>`/`<main>`.
- LLM text always markdown-rendered; code formatted with newlines/indentation (the system prompt requests formatted code).
- No dual representation: each value appears once (e.g. the answer value isn't repeated in both prose and a separate field).
- Body text ≥16px, WCAG-AA contrast, responsive from narrow to wide, no horizontal scroll on the primary flow.

## E2E (Phase 1 gate)
Playwright (`frontend/tests/e2e/upload-ask.spec.ts`) against the live server with the real Gemini key: upload a real CSV → assert the profile card renders → ask a question → assert the answer text, a chart element, a table, the collapsible code panel, and the cost line all appear (not just HTTP 200).
