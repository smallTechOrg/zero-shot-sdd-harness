# Project Layout — Canonical Structure

All projects built from this boilerplate must follow this layout exactly. A standard **Payload CMS v3 + Next.js 16 app** — a single application rooted at the repo, with Payload embedded *inside* the Next app (as scaffolded by `create-payload-app`, then extended) — is the canonical reference.

---

## README Requirements (Mandatory)

Every generated project **must** have a README that:

1. **States "all commands run from the repo root"** — the repo root IS the project (a single Next+Payload app; no subdirectory to cd into). Put this as a blockquote or bold warning at the very top, before any other content.
2. **Runs every command through pnpm** (`pnpm dev`, `pnpm build`, `pnpm start`, `pnpm test`, `pnpm payload ...`) — never bare `next`, `payload`, `vitest`, or `playwright`. Bare commands fail unless the local binaries are on PATH.
3. **Includes a boot/schema verification step after setup** — start the app (`pnpm dev`), then confirm `GET http://localhost:3000/` returns 200 and `/admin` loads. A loading `/admin` proves Payload pushed the schema to Postgres. When production migrations are used, `pnpm payload migrate:status` must list the migration as applied (blank output = silent failure).
4. **Stays accurate** — every README command must be tested before a phase is marked complete. If a command fails, fix the README before claiming the phase is done.

The README is the first thing a user touches. A wrong README fails the entire build regardless of whether the code works.

---

## Source Code Rule (Non-Negotiable)

**All application source code must live inside `src/`.** Never place page components, CSS, React components, Payload collections, or any app-level code at the repo root.

The repo root is for project-level config only: `package.json`, `tsconfig.json`, `next.config.mjs`, `tailwind.config.ts`, `postcss.config.js`, `.env.example`, and boilerplate infrastructure (`spec/`, `harness/`, `CLAUDE.md`). Tests are the one deliberate exception — `tests/` (vitest) and `e2e/` (playwright) sit at the repo root, **not** inside `src/`. If you are about to create an application file at the root, stop and put it under `src/` instead.

This applies to every part of the app — the public marketing site, shared components, and the Payload CMS config alike.

---

## Directory Tree

The repo root **is** the project. There is no `<project-slug>/` subdirectory — boilerplate files (`spec/`, `harness/`, `CLAUDE.md`) coexist with app files at the root.

**One app only.** The skeleton ships a single Next+Payload app under `src/`. **Extend that tree in place** — never stand up a second app beside it, and never split the public site into a separate top-level `frontend/` directory. A parallel app or a second `src/`-like tree is always wrong: it duplicates the wired-up baseline instead of extending it, leaving dead code and two sources of truth.

```
<repo root>                              ← repo root IS the project (one Next + Payload app)
├── src/
│   ├── app/
│   │   ├── (frontend)/                  ← public marketing site routes
│   │   │   ├── globals.css              ← design tokens (CSS custom properties) + @tailwind layers
│   │   │   ├── layout.tsx               ← root layout for the public site
│   │   │   └── page.tsx                 ← home page ("/")
│   │   └── (payload)/                   ← Payload admin + API route groups (from create-payload-app)
│   │       ├── admin/[[...segments]]/   ← /admin UI
│   │       ├── api/[...slug]/           ← Payload REST API at /api
│   │       ├── api/graphql/             ← GraphQL endpoint at /api/graphql
│   │       └── layout.tsx
│   ├── collections/                     ← Payload collections, one file per collection — only if the phase adds any
│   │   └── <Collection>.ts              ← e.g. Properties.ts, Media.ts, Users.ts
│   ├── components/                      ← React/Tailwind components for the public site
│   │   └── <Component>.tsx
│   ├── lib/                             ← shared, non-UI helpers (data fetching, utils)
│   ├── payload.config.ts                ← Payload config: db adapter, collections, admin, editor
│   └── payload-types.ts                 ← GENERATED (pnpm payload generate:types) — do not hand-edit
├── tests/                               ← vitest (unit/integration, incl. Payload local API) — NOT inside src/
│   └── ...
├── e2e/                                 ← playwright (E2E/UI against the running app on :3000)
│   └── ...
├── spec/                                ← project spec files (preserved from boilerplate)
├── harness/                             ← engineering harness (preserved from boilerplate)
├── CLAUDE.md                            ← preserved from boilerplate
├── next.config.mjs                      ← wrapped with withPayload
├── tailwind.config.ts
├── postcss.config.js
├── tsconfig.json                        ← strict: true
├── package.json
├── .env.example                         ← DATABASE_URI, PAYLOAD_SECRET
└── README.md                            ← replaces the boilerplate README
```

**Critical:** `tests/` and `e2e/` are at the repo root — **not** inside `src/`. `vitest.config.ts` must set `test.include` to `tests/**` (not `src/**`), and `playwright.config.ts` must set `testDir: './e2e'`.

---

## Exact File Shapes

### next.config.mjs

The Next config **must** be wrapped with `withPayload` — Payload is the server, not a separate process. Without the wrapper the `/admin` and `/api` route groups do not mount.

```js
import { withPayload } from '@payloadcms/next/withPayload'

/** @type {import('next').NextConfig} */
const nextConfig = {}

export default withPayload(nextConfig)
```

### src/payload.config.ts

The single source of truth for the CMS: the Postgres adapter, the collections array, the admin panel, and the editor. Secrets come from the environment — never hardcoded.

```ts
import { postgresAdapter } from '@payloadcms/db-postgres'
import { lexicalEditor } from '@payloadcms/richtext-lexical'
import path from 'path'
import { buildConfig } from 'payload'
import { fileURLToPath } from 'url'
import sharp from 'sharp'

const filename = fileURLToPath(import.meta.url)
const dirname = path.dirname(filename)

export default buildConfig({
  admin: {
    importMap: { baseDir: path.resolve(dirname) },
  },
  // Collections are registered here as the CMS phase adds them (imported from src/collections/).
  collections: [],
  editor: lexicalEditor(),
  secret: process.env.PAYLOAD_SECRET || '',
  typescript: { outputFile: path.resolve(dirname, 'payload-types.ts') },
  db: postgresAdapter({
    pool: { connectionString: process.env.DATABASE_URI || '' },
  }),
  // Media/storage: local disk in dev; @payloadcms/storage-gcs wired in a later phase.
  sharp,
})
```

### src/collections/&lt;Collection&gt;.ts (add only when the phase needs a collection)

Payload owns the schema through these configs — there is no separate ORM or model file.

```ts
import type { CollectionConfig } from 'payload'

export const Properties: CollectionConfig = {
  slug: 'properties',
  admin: { useAsTitle: 'title' },
  fields: [
    { name: 'title', type: 'text', required: true },
    { name: 'price', type: 'number' },
    { name: 'description', type: 'richText' },
    { name: 'hero', type: 'upload', relationTo: 'media' },
  ],
}
```

Register it in `src/payload.config.ts`: `collections: [Properties, Media]`.

### tailwind.config.ts (the tokens slice)

Tailwind content is **scoped to the frontend** so its base/preflight styles never leak into the Payload admin UI. Colors and fonts map to the CSS custom properties defined in `globals.css`.

```ts
import type { Config } from 'tailwindcss'

export default {
  content: [
    './src/app/(frontend)/**/*.{ts,tsx}',
    './src/components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: 'var(--color-bg)',
        fg: 'var(--color-fg)',
        accent: 'var(--color-accent)',
      },
      fontFamily: {
        display: ['var(--font-display)'],
        body: ['var(--font-body)'],
      },
    },
  },
  plugins: [],
} satisfies Config
```

### src/app/(frontend)/globals.css (the other half of the tokens slice)

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --color-bg: #0b0b0c;
    --color-fg: #f5f5f4;
    --color-accent: #b8975a;             /* luxury gold */
    --font-display: 'Playfair Display', serif;
    --font-body: 'Inter', sans-serif;
  }
}
```

### Phase 1 schema sequence (mandatory, in order)

All commands run from the **repo root** (where `package.json` and `next.config.mjs` live). Payload owns the schema — there is no Alembic, no SQLAlchemy, no autogenerate.

```bash
# 1. Define collections in src/collections/*.ts and register them in src/payload.config.ts.
# 2. Set DATABASE_URI and PAYLOAD_SECRET in .env (the single manual user step, requested at intake).
# 3. Dev: Payload pushes the schema to Postgres automatically on boot.
pnpm dev
#    Confirm http://localhost:3000/admin loads and the first admin user can be created — this proves the schema was pushed.
# 4. Regenerate types after any collection change:
pnpm payload generate:types
# 5. Production only — create and apply a migration, then verify:
pnpm payload migrate:create initial
pnpm payload migrate
pnpm payload migrate:status   # must list the migration as applied, not blank
```

**Phase 1 is not complete until the app boots (`GET http://localhost:3000/` → 200) and `/admin` loads.** For production, blank output from `migrate:status` means no migration was applied.

### tests/property.int.test.ts (Payload local API integration)

Integration tests run against the **real local Postgres** (`DATABASE_URI` from `.env`) via Payload's Local API — never a mock DB and never an alternate driver (no SQLite substitution when production is PostgreSQL). Assert on structural results (shape, key fields, counts), not on exact prose.

```ts
import { getPayload, type Payload } from 'payload'
import config from '@/payload.config'
import { beforeAll, describe, expect, it } from 'vitest'

let payload: Payload

beforeAll(async () => {
  payload = await getPayload({ config })
})

describe('payload local API', () => {
  it('connects to the real Postgres DB and serves a collection', async () => {
    const result = await payload.find({ collection: 'properties', limit: 1 })
    expect(result).toBeDefined()
    expect(Array.isArray(result.docs)).toBe(true)
  })
})
```

### e2e/home.spec.ts (Playwright, against the running app)

```ts
import { expect, test } from '@playwright/test'

test('home page renders', async ({ page }) => {
  const res = await page.goto('http://localhost:3000/')
  expect(res?.status()).toBe(200)
  await expect(page).toHaveTitle(/.+/)
})

test('admin panel loads', async ({ page }) => {
  const res = await page.goto('http://localhost:3000/admin')
  expect(res?.status()).toBeLessThan(400)
})
```

---

## Rules

1. **App code goes in `src/`** (`src/app/**`, `src/components/**`, `src/collections/**`, `src/lib/**`) — never in the boilerplate root
2. **No hand-rolled ORM or raw SQL** — Payload owns the schema and data access. Read/write through the Payload Local API (`getPayload`) or the auto-generated REST/GraphQL endpoints; never add a second ORM or migration tool (no Alembic/SQLAlchemy/Prisma alongside Payload)
3. **Collections live in `src/collections/`** — one file per collection, each registered in the `collections` array of `src/payload.config.ts`, the single source of truth for the schema
4. **Generated types are canonical** — run `pnpm payload generate:types` after any collection change and import entity types from `src/payload-types.ts`; never hand-write them. TypeScript `strict` throughout
5. **Components are typed React function components** in `src/components/`, consumed by routes in `src/app/(frontend)/`; shared non-UI helpers go in `src/lib/`
6. **Design tokens are the tokens slice** — CSS custom properties in `src/app/(frontend)/globals.css` plus their mapping in `tailwind.config.ts`; Tailwind content is scoped to the frontend so it never leaks into the Payload admin UI
7. **Media/storage adapter is configured in `payload.config.ts`** — local disk for dev, `@payloadcms/storage-gcs` wired in a later phase; no cloud creds needed early
8. **Payload auto-generates the API** — REST at `/api`, GraphQL at `/api/graphql`; do not hand-roll CRUD route handlers for collection data
9. **Runtime config comes from `.env`** (`DATABASE_URI`, `PAYLOAD_SECRET`) read by `payload.config.ts` — fail fast at startup if a required var is absent; never hardcode secrets
10. **Phase 2 gate runs against real services** — vitest (incl. the Payload local API) and the golden-path smoke hit the **real local Postgres** and the **real running Next+Payload app** (boot check: `GET http://localhost:3000/` → 200, `/admin` loads). Never gate on a mock DB; there is no LLM key for this project
