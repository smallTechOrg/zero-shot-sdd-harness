# Implementation Phases

Agents are built incrementally. This is the default model; the planner sub-agent adapts it per project.

**Core principle: build the full product first (the Build Phase), then add capabilities.** Phase 1 is
**not** a narrow MVP — it ships the complete product the user described, end-to-end with real
integrations (real LLM, real MCP tools, real local DB) **and its UI**. Put your best shot into Phase 1.
Each later phase **adds a new capability** (or productionises) on top of that live, complete foundation;
later phases do not finish a deferred Phase 1.

**Real-first:** every integration is real from Phase 1. There are no stubs, no offline mode, no stub
banners. CI runs against the real model with a keyed secret and loose assertions. → see
[`patterns/llm-providers.md`](patterns/llm-providers.md).

**Local-first:** Phase 1 runs on one machine with no external service to stand up — SQLite for app
metadata (DuckDB where analytical), provider key in `.env`. PostgreSQL is a later productionising phase.

---

## Default phase model

### Phase 1 — The Full Product (Real, incl. UI)

Implement the **complete product the user described**, end-to-end with real integrations — the full
agentic baseline **plus the UI** and every capability the product needs to be the thing they asked for.
This is the raised baseline: real LLM + local DB schema + ReAct loop + working/short-term memory + ≥1
MCP tool + eval skeleton + **the UI (designed → built → reviewed)** when the product has a user-facing
surface (→ [`ui-and-design.md`](ui-and-design.md)).

**Gate:**
1. DB schema: `uv run alembic upgrade head` succeeds against the configured **local DB** (SQLite by
   default; DuckDB where analytical); `uv run alembic current` shows a revision. Schema includes:
   `runs`, `messages`, and the agent's domain entities.
2. Agent runs end-to-end with the **real LLM**; ≥1 record written to DB; run status `completed`.
3. `pytest` passes using the production DB driver (→ [`tech-stack.md`](tech-stack.md) § Database & Tests),
   fully automated via `conftest.py`. CI uses a real API key (stored in secrets); assertions are loose
   (structure + non-empty) to tolerate LLM output variance.
4. **Golden-path smoke test passes** (if any UI/HTTP surface) — asserts rendered content, not just
   status codes. → [`workflows/golden-path-smoke-test.md`](workflows/golden-path-smoke-test.md).
5. **Live-server smoke:** start the app (`uv run python -m <pkg>`), hit `/health` + one real page with
   `curl`, both 200; log exit codes in the session report.
6. **For ReAct agents:** the loop runs ≥2 iterations in tests (at least one action, then the finish
   tool); a test drives past `max_agent_iterations` into `force_finalize` (best-effort answer, not a
   crash). Observability holds — structured per-`run_id` logs, token/cost on the run, `action_history`
   surfaced to the user. → [`patterns/react-agent.md`](patterns/react-agent.md).
7. **Baseline agentic layers wired:**
   - **Memory** — working + short-term; context assembled in one place. → [`patterns/memory-and-context.md`](patterns/memory-and-context.md).
   - **Tools/MCP** — ≥1 real MCP tool behind the action-safety boundary. → [`patterns/tools-and-mcp.md`](patterns/tools-and-mcp.md).
   - **Evals** — eval-harness skeleton (tiny fixed dataset + ≥1 assertion) runs in CI with the real model, loose asserts. → [`patterns/observability-and-evals.md`](patterns/observability-and-evals.md).
   - **Observability** — OTel GenAI traces wired at baseline. → [`patterns/observability-and-evals.md`](patterns/observability-and-evals.md).
8. Phase 1 includes **all** the capabilities from `spec/product/capabilities/` — not just infrastructure.
9. **UI (if the product has a user-facing surface):** built from `spec/product/06-ui.md`, **designed**
   (by spec-writer) and **reviewed** (by spec-reviewer's UI pass) per [`ui-and-design.md`](ui-and-design.md),
   served by the app, and verified in a real browser — a **Playwright test asserts the post-JavaScript
   DOM** (rendered content, not just status codes). The UI is a Phase-1 gate item, never deferred.
10. Tree clean and committed + pushed.

> **Phases 2+ ADD CAPABILITIES** to the complete product Phase 1 already shipped — they do not finish a
> deferred Phase 1. The UI, the core capabilities, the golden-path and a browser-level test all land in
> Phase 1; what follows is hardening, new capabilities, productionising, and polish. The planner picks
> and orders the ones the project needs.

### Phase 2 — Error Handling + Resilience

Add try/catch, retries, timeouts to all external calls; degrade rather than crash on non-critical
failures. **Gate:** all documented failure modes handled without crashing.

### Phase 3 — New Capabilities / Additional Integrations

Add capabilities or integrations beyond the Phase-1 product (each spec'd first via
`/spec-new-capability`). **Gate:** each new capability real and end-to-end; its own tests pass.

### Phase 4 — Productionising (e.g. PostgreSQL, deploy)

When the project outgrows local: migrate the DB to **PostgreSQL** (driver/URL change + `pgvector` if
needed), add a durable checkpointer (`PostgresSaver`), hosting/deploy concerns, multi-user auth.
**Gate:** the full suite passes against the production driver; `alembic upgrade head` on Postgres.

### Phase 5 — Advanced Observability

The structured-logging + token/cost + OTel baseline already lands in Phase 1. This phase adds
aggregation: per-run metrics, latency dashboards, a richer eval suite (LLM-judge, component evals),
and a regression gate. **Gate:** per-run token, cost, and latency are queryable in aggregate; errors
carry `run_id`; regression threshold set and enforced in CI.

### Phase 6 — Polish + Hand-off

Fix rough edges, improve error messages, update docs. Final drift audit; accurate README.
**Gate:** drift audit passes; README reviewed by user; user accepts hand-off.

---

## Agentic layers by phase

The baseline layers (memory, MCP tools, evals, OTel) **and the UI** land **real in Phase 1**. The
earns-its-place layers land in a later phase, each only when `02-architecture.md` says the agent needs
it:

| Layer | Lands at | Trigger |
|-------|----------|---------|
| Retrieval / RAG ([`patterns/retrieval.md`](patterns/retrieval.md)) | Phase 3+ | answers depend on a corpus or cross-session knowledge |
| Long-term memory | Phase 3+ | answers depend on cross-session episodic/semantic memory |
| Human-in-the-loop ([`patterns/guardrails-and-hitl.md`](patterns/guardrails-and-hitl.md)) | Phase 2+ | the agent gains a real irreversible/high-stakes action |
| Durable execution / checkpointing ([`patterns/durability.md`](patterns/durability.md)) | Phase 4+ | runs become long, resumable, or must survive a restart (with productionising) |
| Multi-agent topologies ([`patterns/multi-agent.md`](patterns/multi-agent.md)) | Phase 3+ | an escalation criterion is met |
| Richer evals + LLM-judge ([`patterns/observability-and-evals.md`](patterns/observability-and-evals.md)) | Phase 5 | regression gate / answer-quality validation needed |

---

## Phase gates

A phase is complete when ALL hold: code committed and pushed · tests pass · tree clean · session report
updated · qa-auditor (or manual checklist) signed off. For Phase 1 specifically, `alembic upgrade head`
has been run against the real DB and confirmed.

**Never mark a phase complete with any gate red.** Never claim a pass on tests that use a different DB
driver than production (→ `tech-stack.md` § Database & Tests).

The current phase is recorded in the active session report and in commit messages (`phase-N: …`);
`git log --oneline | grep "phase-"` shows the history.

## Adapting the phases

The planner may merge, split, or reorder the later phases (a pure CLI tool has no UI to build in Phase 1;
a no-DB project shrinks the schema work; a multi-capability project splits Phase 3). The core principle
holds: **Phase 1 ships the full product — real integrations, local-first, UI included.**

---

## Language-specific gate commands

The gate command depends on the language; the tech-designer sets it in `tech-stack.md`, the planner uses
it in phase definitions.

| Language | Phase 1 gate |
|----------|-------------|
| Python | `uv run alembic upgrade head` + `uv run pytest` (real API key in env) |
| TypeScript (Bun) | migration tool + `bun test` |
| TypeScript (Node) | migration tool + `npx vitest run` |
| Go | `migrate up` + `go test ./...` |

CI must have the LLM API key set as a secret. Tests use the real model with **loose assertions** (check
structure + non-empty output, not exact strings) so normal LLM output variance doesn't flap the build.
