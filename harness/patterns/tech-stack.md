# Tech-Stack Rules

Generic engineering rules that hold for **every** project, whatever stack is chosen — Python, TypeScript,
Go, Ruby, a static site generator, anything. The project's *chosen* stack (language, framework, LLM
provider/model if any, database, libraries) is recorded in `spec/architecture.md` under `## Stack`. This
file is the permanent doctrine the spec-writer (filling the `## Stack`) and the code-generators
(implementing against it) follow — it is not edited per project.

---

## Dev Port / Local Run Rule

Pick a dev port that doesn't collide with other common local services (e.g. avoid the framework's bare
default if it commonly clashes — port 8000 is often taken by other local dev servers). Whatever port is
chosen:

- The chosen port is hard-coded (or defaulted) in the app's entry point, not left to chance
- README must reference the actual URL the app serves on
- `.env.example` should include the port if it's configurable

## Frontend Build & Serve Rule

**Whenever the frontend requires a build step before it can be served correctly** (a static export, a
bundled SPA, a compiled asset pipeline — whatever this project's frontend actually is, per
`spec/architecture.md`), three things are mandatory — each has been a real first-build failure class in
practice:

- **The documented run path is the one the user and the gate both use.** If the deployment model is
  "build once, serve the built output" (e.g. `next build` with `output: 'export'` mounted under a
  sub-path by the backend), the README and the gate must use that exact path — not a convenient
  alternative dev server on a different port/origin that happens to work locally but isn't how it ships.
  Handing the user a dev-only flow that diverges from the real deploy path reads as "nothing loads" when
  they follow the README literally.
- **The CSS/JS pipeline must actually run, not just exit 0.** Whatever this project's styling toolchain is
  (Tailwind, Sass, CSS Modules, vanilla), code-generators must never replace or omit the config files that
  wire it up, and the gate must verify the built output contains real compiled styles/selectors — not just
  check for an HTTP 200.
- **Runtime-version safety.** Pin the language/runtime version this project needs (`.nvmrc`, `.tool-versions`,
  a lockfile-declared engine range, etc.) and document any known footgun for that version (e.g. a specific
  Node major version breaking a global API some framework relies on). A project with no pinned version is
  one upgrade away from an environment-specific failure nobody can reproduce.
- **Automated E2E for any project with a frontend.** Every frontend build must include an automated
  browser-driven smoke suite (Playwright, Cypress, or the ecosystem-standard equivalent) covering: page
  loads and is styled, primary input works, real output appears (not a spinner or error state). Record the
  exact gate command in `spec/roadmap.md`. **A frontend gate that only checks HTTP 200 or a CSS selector
  grep is not a gate — the browser-driven suite must also pass.**

## LLM Model Name Rule (only if this project has an LLM/AI dependency)

**Always use a current, verified model name — never a deprecated or guessed one.**

- Model names change. Before hardcoding any model identifier, verify it exists by calling the provider's
  `ListModels` API or checking current documentation.
- The model name must be configurable via an env var (e.g. `APPNAME_LLM_MODEL`) so it can be changed
  without a code deployment.
- A 404 NOT_FOUND from the LLM API almost always means the model name is wrong — check the name first
  before debugging anything else.

Record the actually-chosen provider and model in `spec/architecture.md` → `## Stack`; this file does not
hardcode a default, since not every project has an LLM dependency at all.

## DB Driver Rule (only if this project has a database)

The database driver (e.g. `psycopg2-binary`/`asyncpg` for PostgreSQL, `pg` for Node, `lib/pq` for Go)
**must be declared as a main/production dependency**, never in a dev-only dependency group.

Reason: migrations run at deploy/setup time, not just in tests. If the driver is dev-only, migrations
fail in any environment that didn't install dev deps.

## Test Environment Rule (only if this project has a database)

**Tests must use the same database engine as production.** If the production DB is PostgreSQL, tests run
against PostgreSQL — not SQLite, not an in-memory substitute.

- Tests that pass on a lightweight substitute but were never run against the production engine are **not
  a passing gate**.
- The test database must be set up automatically. Use whatever this stack's equivalent of `conftest.py`
  is (a test setup/teardown hook, a fixture file) to create and tear down the test database — no manual
  steps.
- The test DB URL is provided via env var (e.g. `TEST_DATABASE_URL`, or reuse `DATABASE_URL` pointing at a
  `_test` database). The test setup creates all tables before tests and drops them after.
- A `.env.test` file (gitignored) or CI environment variable provides the test DB URL. The README must
  document this.

## LLM / External-API Test Rule (only if this project calls a real external provider)

**Tests and gates run against the real dependency using credentials loaded from `.env`.** There is no
offline-passing requirement; real-credential execution is the default and required path for every gate,
against the production-shaped database (never a lightweight substitute if production is PostgreSQL). A
stub provider MAY exist as an optional local fallback when a credential is genuinely absent, but it is
never the gate. The quality bar is perfect, zero errors — edge-case, end-to-end, and UI tests are
required, not optional.

- The build and tests load credentials programmatically from `.env` (gitignored); confirm a credential by
  presence (bool) only — never echo, print, paste, or commit a secret value.
- A stub is permitted only for an integration whose external system isn't built yet — never as a
  substitute for the real provider on a path that exists.
- **CI contract:** a runner without secrets cannot pass the real-credential gate. Either inject the
  credentials from a secret store, or guard the real-credential tests with a skip when they're unset.
  Skipped is not passed: the gate for any phase that needs a missing credential is BLOCKED until it's
  provided locally.

Projects with no external LLM/API dependency (a static site, an internal CRUD tool with no third-party
calls) simply have no surface for this rule — don't invent a substitute requirement.
