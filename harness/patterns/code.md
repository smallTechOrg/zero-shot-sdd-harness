# Code Style

> Generic code conventions that apply to **every** project — harness doctrine the code-generator and code-generator follow, not a per-project file. The language-specific sections are reference; this project's chosen language/stack is in `spec/architecture.md` (`## Stack`).

---

## Universal Rules

These apply regardless of language or framework:

1. **Types at boundaries** — every function that crosses a module boundary must use typed inputs and outputs (TypeScript interfaces, Zod schemas, Go structs, etc.) — never raw dicts or `any`
2. **One responsibility per file** — a file does one thing; if it's doing two things, split it
3. **No comments explaining WHAT** — code should be self-documenting via names; only comment WHY something non-obvious is done
4. **No dead code** — remove unused imports, functions, and variables immediately; don't comment them out
5. **Fail loudly at startup** — validate all required config/env vars at startup; don't fail silently at runtime
6. **No hardcoding** — values that could change (URLs, limits, credentials) go in config or environment variables

## Naming Conventions

<!-- FILL IN: Filled in by spec-writer based on language choice. -->

## File Organization

<!-- FILL IN: Filled in by spec-writer. How are files grouped — by layer, by feature, by type? -->

## Error Handling Pattern

<!-- FILL IN: Filled in by spec-writer. How are errors represented and propagated? -->

## Logging Pattern

<!-- FILL IN: Filled in by spec-writer. Structured vs. unstructured? What fields are always included? -->

## Testing Conventions

<!-- FILL IN: Filled in by spec-writer. Unit test location, naming, runner. -->

## What NOT to Do

<!-- FILL IN: Anti-patterns specific to this tech stack. Filled in by spec-writer. -->

---

## Test Environment Rules

These apply to all projects. No exceptions.

1. **Same DB as production** — if the app uses PostgreSQL, tests use PostgreSQL. SQLite is not a substitute. A test suite that only passes on SQLite tells you nothing about whether migrations and queries work against the real database.

2. **Automated setup — no manual steps** — the Vitest global setup (`tests/setup.ts` / `globalSetup`) must bring up the schema (Payload dev push against the test DB) and tear it down automatically. The test runner must work with a single command — `pnpm test` (vitest run) — after setting the test DB URL.

3. **Isolated test database** — use a dedicated database (e.g. `myapp_test`, not `myapp`). Never run tests against the development or production database.

4. **Test DB URL via environment** — expose the test database URL through the same env var mechanism as the app (e.g. `DATABASE_URI` pointing at the test DB, or a `TEST_DATABASE_URI` that the Vitest setup reads). Document this in the README.

5. **DB URL and secrets in `.env.example`** — the `.env.example` file must include the test DB URL and every required secret with clear placeholders (e.g. `PAYLOAD_SECRET=`, `DATABASE_URI=`) so the user knows what to fill in. This project has no LLM/API key — the secrets are `PAYLOAD_SECRET` and `DATABASE_URI` (plus GCS credentials later). Filling `.env` with real values is the only manual user step, requested at intake; tests load these programmatically and confirm them by presence only.

6. **Payload owns the schema — migrations in CI / README** — in dev, Payload pushes schema changes automatically (dev push); for production, the README/CI must include generating and applying migrations (`pnpm payload migrate:create` then `pnpm payload migrate`) as an explicit step before running the app or tests. Never rely on dev push (auto-schema-sync) alone in production; there is no Alembic and no SQLAlchemy metadata auto-create.

---

## Framework Gotchas (keep up to date — known footguns)

### Next.js 16 App Router — `params`/`searchParams` and dynamic APIs are async

In the Next.js 16 App Router, route `params` and `searchParams` (and `cookies()`, `headers()`, `draftMode()`) are **async** — they return Promises and must be awaited. Reading them synchronously yields `undefined` or throws.

```tsx
// CORRECT (Next.js 16)
export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  // ...
}

// WRONG (pre-15 form) — params is a Promise, not a plain object
export default function Page({ params }: { params: { slug: string } }) {
  const slug = params.slug // undefined
}
```

Fetch Payload data from Server Components via the local API — `const payload = await getPayload({ config })` — never an HTTP round-trip to your own `/api` route.

---

## Integration Test Patterns

Integration and e2e tests exercise the **real** Payload local API against a real local PostgreSQL database — the DB is NOT mocked and SQLite is never substituted. The suite is overly tested: edge cases, error paths, end-to-end journeys, and (for any UI surface) UI states are all required. Integration/e2e assertions check stable structural properties (status, shape, key fields, persisted rows) rather than volatile details; unit tests stay fully deterministic (inject the clock, seed randomness). Run against the production DB driver (`@payloadcms/db-postgres`), never SQLite and never an in-memory DB.

### Stubbing an async startup function in tests

When you replace an async startup function (e.g. an async `seedDatabase()` the app runs before serving) with a Vitest mock, give the mock an **async** implementation. A bare `vi.fn()` returns `undefined`; if the caller `.then()`-chains the result instead of `await`-ing it, that throws `Cannot read properties of undefined (reading 'then')`.

```ts
import { vi } from 'vitest'

// CORRECT — resolves like the real async function
vi.mock('@/lib/bootstrap', () => ({
  seedDatabase: vi.fn(async () => {}),
}))

// WRONG — vi.fn() returns undefined; a `.then()` on it throws
vi.mock('@/lib/bootstrap', () => ({
  seedDatabase: vi.fn(),
}))
```

### Resetting the database between integration tests

Use a Vitest `beforeEach` that talks to the Payload local API against the `_test` PostgreSQL database — the Vitest analogue of an autouse fixture — so each test starts from a known state:

```ts
import { beforeEach } from 'vitest'
import { getPayload, type Payload } from 'payload'
import config from '@payload-config'

let payload: Payload

beforeEach(async () => {
  payload = await getPayload({ config })
  // clear collections so each test starts clean
  await payload.delete({ collection: 'properties', where: { id: { exists: true } } })
})
```

Point `DATABASE_URI` at a dedicated `_test` PostgreSQL database — the real production driver, never SQLite and never an in-memory DB — so migrations and queries are exercised for real. For Playwright E2E, do the equivalent seed/teardown in a fixture (`test.extend`) or global setup rather than inline in each spec.

---

## Typed Config Module — Validate Env at Startup

There is no `pydantic-settings` here. Read env through a single typed config module that validates every required variable **at module load** and throws if one is missing — so the process fails loudly at startup, not at the first request. Node's `process.env` never rejects unknown keys, so extra variables in `.env` (`TEST_DATABASE_URI`, `EDITOR`, CI vars) are harmless and need no `extra="ignore"` equivalent — but you must still assert presence of the ones you own.

```ts
// lib/config.ts — the ONLY place process.env is read
function required(name: string): string {
  const value = process.env[name]
  if (!value) throw new Error(`Missing required env var: ${name}`)
  return value
}

export const config = {
  payloadSecret: required('PAYLOAD_SECRET'),
  databaseUri: required('DATABASE_URI'),
} as const
```

Import `config` everywhere instead of touching `process.env` directly. (A schema validator such as Zod is an acceptable upgrade for richer types/coercion — the non-negotiable is: one typed module, validated at startup, that fails loudly on a missing required var.) This is mandatory for any project whose `.env` contains variables owned by other tools (test runners, editors, CI, Docker, etc.).

---

## Route Errors — Use App Router Boundaries and Payload Errors

When a Server Component or route handler hits a failure (a data fetch fails, a record is missing, validation rejects input), don't hand-render a bare JSON error body or swallow it. Use the App Router's built-in boundaries plus Payload's own error surfaces:

- **`error.tsx`** — catches errors thrown anywhere in a route segment and renders a readable page with a `reset()` retry affordance.
- **`not-found.tsx` + `notFound()`** — for missing records (e.g. an unknown property slug), rendering a proper 404 page.
- **Payload access control and field `validate` functions** enforce authz/validation at the data layer; let their errors propagate to these boundaries rather than catching and discarding them.

```tsx
// app/properties/[slug]/page.tsx
import { notFound } from 'next/navigation'
import { getPayload } from 'payload'
import config from '@payload-config'

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const payload = await getPayload({ config })
  const { docs } = await payload.find({
    collection: 'properties',
    where: { slug: { equals: slug } },
    limit: 1,
  })
  if (!docs.length) notFound()   // → renders not-found.tsx
  // any thrown/awaited error below bubbles to error.tsx
  return <PropertyView property={docs[0]} />
}
```

Every route segment that fetches data must have an `error.tsx` boundary (and a `not-found.tsx` wherever records can be missing) so failures render a readable page with a way back — never an unhandled exception or a raw 500 JSON response.
