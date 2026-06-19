# UI & Design — Canonical Home

**Layer 10's user-facing surface.** When a product the user describes has any UI, that UI is a
**Phase-1 deliverable** ([`ai-agents.md`](ai-agents.md) § 13, [`phases.md`](phases.md) § Phase 1) — it
is **designed, built, and reviewed** as part of the workflow, never deferred. This file defines what
"good UI" means here, the design→build→review loop, and the usability checklist. The screens themselves
are spec'd per-project in [`../product/06-ui.md`](../product/06-ui.md).

---

## Why this exists

For most products the user describes, **the UI is the product** — it's how they actually use the thing.
A working backend behind no (or a bad) UI is not the product they asked for. So UI quality is a first
-class requirement, with its own design and review steps in the build, not an afterthought bolted on at
the end.

## The loop: design → build → review

1. **Design (spec-writer)** — before building the frontend, the spec-writer produces/confirms
   [`../product/06-ui.md`](../product/06-ui.md) (every screen, state, and flow) and a short **design
   direction**: layout & information hierarchy, the primary user journey, and how each of the required
   states is handled (see checklist). Keep it lightweight — a clear plan, not a design system. (UI
   design is part of the spec-writer's job — there is no separate UI agent.)
2. **Build** — implement per [`project-layout.md`](project-layout.md): **Next.js 15 + React + Tailwind**
   under `frontend/`, **served by the app** so the whole product runs on one port/command. Wire every
   spec'd screen, the live agent trace, and all loading/empty/error states. Talk to the API over the
   `ok()`/`api_error()` envelope + SSE.
3. **Review (spec-reviewer)** — the spec-reviewer drives the real UI in a browser (Playwright),
   **captures a screenshot of each primary screen**, and checks it against the design + the usability
   checklist below. File concrete fixes; the builder addresses them before the Phase-1 gate. (UI review
   is part of the spec-reviewer's job — see its § UI Review.)

## Usability checklist (what "user-friendly" means here)

A UI passes review when all hold:

- **Clear primary action.** On each screen it's obvious what to do next; the main path isn't buried.
- **Every state is handled** — **empty** (no data yet, with a prompt to act), **loading** (explicit
  indicator; for agent runs, the **live step trace**, not an opaque spinner —
  [`patterns/react-agent.md`](patterns/react-agent.md) § User transparency), **error** (the
  envelope's message shown inline + a recovery path), and **success**.
- **Legible & consistent** — readable type and spacing, consistent components, sane responsive layout;
  no overlapping or cut-off content at common widths.
- **Feedback on every action** — clicks/submits visibly do something; disabled controls explain why.
- **Results are rendered, not dumped** — tables/charts/structured output are formatted, not raw JSON.
- **The whole product is reachable from the UI** — every Phase-1 capability has a way to be used.
- **No dead ends** — errors and empty states always offer a next step.

## Tech & serving

- **Stack:** Next.js 15 + React + Tailwind (frontend is always Node.js, never Python —
  [`tech-stack.md`](tech-stack.md)). Charts: a standard React chart lib (e.g. Recharts) when the
  product visualizes data.
- **One process, one port (local-first).** Default to **serving the built UI from the app** (e.g. a
  static export mounted by the API) so `uv run python -m <pkg>` brings up the whole product on one
  port. A separate dev server is fine for iterating, but the shipped Phase-1 experience is single
  -command. SSE is consumed via the fetch `ReadableStream` (note SSE framing uses CRLF) — see
  [`../product/05-api.md`](../product/05-api.md).

## Testing the UI (Phase-1 gate)

Any client-rendered content (SPA, charts, streamed tokens) is verified with a **real browser
(Playwright)** asserting the **post-JavaScript DOM** — a `TestClient` HTML check cannot see what the
browser paints ([`ai-agents.md`](ai-agents.md) § 7). At least one test drives the whole stack as a user
does (browser → API → agent → DB → back), nothing mocked, the model real. This is a Phase-1 gate item
([`phases.md`](phases.md)).

## Phasing

The UI ships **in Phase 1** when the product has a user-facing surface — designed + built + reviewed.
Later phases may add screens for new capabilities or polish, but the core UI is not a later phase.
A headless product (pure CLI / webhook / schedule, no user-facing surface) has no UI step — confirm
that at intake (`agent-builder` Q3) rather than assuming it.
