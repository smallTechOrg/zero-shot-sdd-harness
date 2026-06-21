# Recipes — proven, version-stamped scaffolds the planner names and the executor copies

A **recipe** is a tested starter scaffold for one stack rung. The **planner names the recipe**
in the step plan; the **executor copies it** into `src/`/`ui/` and adapts it to the spec — it
does not invent the scaffold from scratch. Recipes are the *proven code*; the
[`../../spec/patterns/`](../../spec/patterns/) usage-spec files are the *API-shape
guardrails* the executor reads before writing the domain seams a recipe leaves open. (Recipes
are canonical method and stay in `harness/`; the usage-specs are a project artefact in `spec/`,
established/edited as part of a feature request.)

## The three recipes

| Recipe | Stack | Use it for |
|---|---|---|
| [`python-fastapi-duckdb`](python-fastapi-duckdb/) | FastAPI · LangGraph · **DuckDB** (+ SQLite spine) | **Analytics** — columnar/OLAP queries over uploaded CSV/JSON/Parquet; local-first, single-file, zero-ops |
| [`python-fastapi-sqlite`](python-fastapi-sqlite/) | FastAPI · LangGraph · **SQLite** (async, `create_tables()`) | **Relational** — durable rows, transactions; local-first, single-file, zero-ops |
| [`frontend-nextjs`](frontend-nextjs/) | Next.js (App Router) · React · Tailwind · react-markdown | **UI** — the chat/upload/markdown/trace-link web shell; plain JS, no TS toolchain |

## Stack-conditional selection (how the planner picks)

| If the spec needs… | Name this recipe |
|---|---|
| OLAP / analytics over files (CSV/JSON/Parquet), aggregations, "data agent" | `python-fastapi-duckdb` |
| relational/transactional rows, durable local state | `python-fastapi-sqlite` |
| a web UI (any of the above with a browser front-end) | `frontend-nextjs` (alongside the backend recipe) |

The backend recipes are **mutually exclusive** (pick the store the data shape demands); the
frontend recipe is **additive** — pair it with whichever backend the spec needs.

> **A mismatched recipe is how the slow build lost.** Naming the wrong scaffold (a relational
> SQLite recipe for an analytics file-query workload, or vice-versa) forces the executor to
> fight the scaffold instead of filling its seams — re-plumbing the DB layer, re-deriving the
> query path. The planner's recipe choice is load-bearing: name the rung that matches the data
> shape, and the build is mostly seam-filling; name the wrong one and it's a rewrite.

## Version-stamp + re-sync convention

Every recipe carries a **version stamp** (libs + date) in its `README.md` — the same contract as
the usage-specs:

> **A stale scaffold is a confidently-wrong start.** When an upstream lib moves past a recipe's
> stamp, **re-prove the recipe green** (run its gate — tests pass, server boots, build succeeds)
> against the new versions **before re-stamping**. Never bump the stamp on faith; a recipe that
> looks current but no longer runs is worse than one honestly marked stale, because the executor
> trusts it.

Re-sync steps when a pinned lib bumps:
1. Update the recipe's deps to the new version.
2. Run the recipe's **gate** (the `## Phase N gate` / quickstart in its README) — it must be green.
3. Fix any drift the new version introduced; refresh the matching
   `spec/patterns/<lib>.md` in the **same** change (the usage-spec and the recipe move
   together — across the `harness/`↔`spec/` boundary).
4. Only then update the stamp (libs + date) in the recipe README.

## What is intentionally NOT shipped

There is **no Postgres/server-DB recipe, no Node-backend recipe, and no Go recipe** — and that is
deliberate. Local-first means **SQLite or DuckDB**; a server DB is added only when a spec genuinely
needs one. No build to date has needed any of them, and an unproven scaffold is dead weight that
rots silently. Recipes are added on the **first real demand** (a spec that genuinely needs the
rung), proven green, then stamped — never speculatively. Keep this set small and honest; breadth
that no build exercises is the bloat the harness exists to avoid.
