# Tech-Stack Rules

Generic engineering rules that hold for **every** project, whatever stack is chosen. The project's *chosen* stack (language, framework, database, libraries) is recorded in `spec/architecture.md` under `## Stack`. This file is the permanent doctrine the spec-writer (filling the `## Stack`) and the frontend/code-generators (implementing against it) follow — it is not edited per project.

---

## Default Dev Port

All generated projects **must** use **port 3000** as the default development port — the Next.js default.

Reason: the Silverwave app is a single Next.js 16 (App Router) + Payload CMS v3 server. `pnpm dev` boots the Next dev server on port 3000; `pnpm build && pnpm start` serves the production build on the same port. The public site is at `/`, the Payload admin at `/admin`, and the Payload REST/GraphQL API at `/api`. There is no separate backend process, no port 8001, and no `/health` route.

- Dev is `pnpm dev` (Next dev server); prod is `pnpm build && pnpm start` — both on port 3000 unless overridden by the `PORT` env var
- README must reference `http://localhost:3000`
- `.env.example` should include `PORT=3000` if the port is configurable
- The boot/health check is `GET http://localhost:3000/` returning 200 (and `/admin` for the CMS phase) — there is no `/health` endpoint

## Frontend Server & Styling Rule

The frontend is **not** a static export served by a separate backend — the Next.js 16 (App Router) app *is* the server, with Payload CMS v3 embedded inside it. It serves the public marketing site at `/`, the Payload admin at `/admin`, and Payload's REST/GraphQL API at `/api`, all from one process on port 3000. Four things are mandatory — each was a real first-build failure:

- **Single-origin is the canonical run + test path.** The user (and the gate) runs **one** server: `pnpm dev` for the inner loop, or `pnpm build && pnpm start` for the production-shaped path, then opens **`http://localhost:3000/`** (public site), **`/admin`** (CMS), and **`/api`** (data). There is no `/app` basePath, no `output: 'export'`, and no second backend process — do **not** invent a two-server flow.
- **Tailwind v3.4 requires `tailwind.config.ts` (with `content` globs covering `src/**`), a `postcss.config` file (plugins: `tailwindcss`, `autoprefixer`), and the `@tailwind base; @tailwind components; @tailwind utilities;` directives in `src/app/(frontend)/globals.css`.** Design tokens live as CSS custom properties in `globals.css` plus the `theme` extension in `tailwind.config.ts`. Without the config, the PostCSS plugins, and the directives, the built CSS has no utility classes — the UI renders unstyled even though the build exits 0. **Code-generators must never replace or omit these files** — extend `globals.css` below the token/directive lines and extend `tailwind.config.ts`, never overwrite them. The gate must verify the built CSS contains real utility selectors, not just check HTTP 200.
- **Node-version safety.** Node ≥25 exposes a broken global `localStorage` unless `--localstorage-file` is set, which crashes Next SSR (`localStorage.getItem is not a function` → every page 500s). The `dev`/`build`/`start` scripts in `package.json` must carry `NODE_OPTIONS=--no-experimental-webstorage` (or the project must pin a supported Node LTS — Node 20+ — via `.nvmrc`/`engines`).
- **Playwright E2E (required for any project with a frontend).** Every build must include an `e2e/` directory with Playwright smoke tests. Install via `pnpm add -D @playwright/test && pnpm exec playwright install --with-deps chromium` (chromium only is sufficient for the gate). The Phase 1 smoke must cover: the page loads and is styled, key navigation/interaction works, and real rendered content appears (not a spinner, error, or unstyled fallback). Gate command: `pnpm exec playwright test e2e/ --reporter=line` (or `pnpm test:e2e`), run against the live app on :3000. **A frontend gate that only checks HTTP 200 or CSS selectors is not a gate — Playwright must also pass.**

## LLM Model Name Rule

**Not applicable to this project.** Silverwave is a luxury real-estate marketing website — there is no LLM, no agent graph, and no model identifier to pin anywhere, so there is nothing to verify or make configurable here. If a future phase ever introduces an LLM integration, restore a verified-model-name rule (verify against the provider's `ListModels`/docs, make it env-configurable, treat a 404 as a wrong name); until then this section imposes no requirements.

## DB Driver Rule

The Postgres adapter (`@payloadcms/db-postgres`, which pulls in its own `pg` driver) **must be declared in `dependencies`** in `package.json`, never in `devDependencies`.

Reason: Payload migrations run at deploy/setup time, not just in tests — and the Payload app connects to Postgres at boot. If the adapter is dev-only, `pnpm payload migrate` (and the running app itself) fails in any environment that didn't install dev deps. Payload owns the schema through its collection configs — there is no Alembic and no standalone migration tool; schema changes go through `pnpm payload migrate:create` / `pnpm payload migrate` (with dev push handling local dev).

## Test Environment Rule

**Tests must use the same database driver as production.** If the production DB is PostgreSQL, tests run against PostgreSQL — not SQLite.

- Tests that pass on SQLite but were never run against PostgreSQL are **not a passing gate**.
- The test database must be set up automatically. Use a Vitest setup file (Payload's local API creates and pushes the schema on connect) to bring the test database up and tear it down — no manual steps.
- The test DB URL is provided via env var (`DATABASE_URI`, pointing at a dedicated `_test` database). The Vitest setup instantiates Payload before tests and disposes the connection after.
- A `.env.test` file (gitignored) or CI environment variable provides the test DB URL. The README must document this.

Example Vitest setup pattern for PostgreSQL + Payload local API:

```typescript
// tests/setup.ts (referenced from vitest.config.ts setupFiles)
import { getPayload, type Payload } from 'payload'
import config from '@/payload.config'

let payload: Payload

beforeAll(async () => {
  // DATABASE_URI must point at a real Postgres _test database.
  // The @payloadcms/db-postgres adapter pushes the schema derived from the
  // collection configs on first connect, so no separate migration step is
  // needed to stand the test database up.
  payload = await getPayload({ config })
})

afterAll(async () => {
  await payload.db.destroy()
})
```

The `DATABASE_URI` in `.env` (or `.env.test`) must point at a real PostgreSQL test database before running tests.

## Real-Dependency Test Rule

**Tests and gates run against the real local Postgres and the real Payload app — never a mock or in-memory database.** There is no LLM in this project, so there is no model key to load; the "real" dependency every gate must exercise is the running Next + Payload app backed by real PostgreSQL (and, in a later phase, real Google Cloud Storage). There is no offline-passing requirement; real execution is the default and required path for every gate, against the production DB driver (never SQLite as a substitute for PostgreSQL). A mock MAY exist as an optional local fallback for a system that isn't built yet, but it is never the gate. The quality bar is perfect, zero errors — edge-case, end-to-end (Playwright), and Payload local-API integration tests are required, not optional.

- The build and tests load `DATABASE_URI` (and, later, GCS credentials) programmatically from `.env` (gitignored); confirm a value by presence (bool) only — never echo, print, paste, or commit a secret value.
- A mock or stub is permitted only for an external system whose integration isn't built yet (e.g. GCS before storage is wired) — never as a substitute for the real Postgres/Payload on a path that exists.
- **CI contract:** a runner without a reachable Postgres cannot pass the real-DB gate. Either provision a Postgres service for CI, or guard the DB-dependent tests to skip when `DATABASE_URI` is unset. Skipped is not passed: the Phase 2+ gate is BLOCKED if the real database is missing locally.
