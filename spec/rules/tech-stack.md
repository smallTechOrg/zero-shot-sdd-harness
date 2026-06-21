# Tech Stack

Filled in by the researcher/planner after the product spec is approved.
The user may override any choice before sign-off.

---

## Language

<!-- FILL IN: e.g., Python 3.12 / TypeScript 5 / Go 1.22 -->

**Why:** <!-- reason -->

## Agent Framework

<!-- FILL IN: e.g., LangGraph / CrewAI / AutoGen / custom / none -->

**Why:** <!-- reason -->

## LLM Provider

<!-- FILL IN: e.g., Anthropic Claude / OpenAI GPT / Google Gemini -->

**Model:** <!-- specific model — see Permanent Rules below for safe defaults -->

**Why:** <!-- reason -->

## Backend Framework

<!-- FILL IN: e.g., FastAPI / Express / Django / none -->

## Database

<!-- FILL IN: e.g., PostgreSQL / SQLite / Redis / none -->

**ORM/ODM:** <!-- e.g., SQLAlchemy 2.0 / Prisma / none -->

## Frontend

<!-- FILL IN: e.g., Next.js 15 / React / Vue / none -->

## Key Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| | | |

## Dependency Management

<!-- FILL IN: e.g., uv + pyproject.toml / npm / pnpm / go modules -->

## What to Avoid

<!-- FILL IN: libraries, patterns, or approaches explicitly off-limits and why -->

---

## Permanent Rules

These apply to all projects regardless of stack choice.

### Default dev port: 8001

Use port **8001** (not 8000 — commonly occupied by other local services).

- `__main__.py` hard-codes `port=8001` unless overridden by env var
- README references `http://localhost:8001`
- `.env.example` includes `PORT=8001` if the port is configurable

### LLM model names

Always use a current, verified model name — verify via `ListModels` or provider docs
before hardcoding. Make the model name configurable via env var (e.g. `APPNAME_LLM_MODEL`).
A 404 NOT_FOUND from the LLM API almost always means the model name is wrong.

Current safe defaults (2026):

| Provider | Default model |
|----------|---------------|
| Google Gemini | `gemini-2.5-flash` |
| OpenAI | `gpt-4o-mini` |
| Anthropic | `claude-3-5-haiku-latest` |

### DB driver in production dependencies

The DB driver (e.g. `psycopg2-binary`, `asyncpg`) must be in `[project.dependencies]`,
never dev-only. Migrations run at deploy time — a dev-only driver breaks them.

### Tests use the same DB as production

If production uses PostgreSQL, tests use PostgreSQL. SQLite is not a substitute.
Tests must be fully automated (`conftest.py` creates and tears down). No manual setup.
