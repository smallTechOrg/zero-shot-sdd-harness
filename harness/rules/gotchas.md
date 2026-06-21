# Gotchas — encoded institutional memory

Hard-won fixes from real builds. Each one was a live failure that cost rework. **Read the
section for your stack before Iteration 0** — the point of this file is that a build never
re-derives a trap a previous build already paid for.

Each entry has a stable **ID** (so gates and reviews can cite it), then **Trap → Fix**. When
a build hits a *new* trap, add an entry here (same shape, next ID) before closing the build —
that is how the harness stays smarter than any single run. The recipes and the reviewer gate
reference these IDs; see [working-with-llms.md](../patterns/working-with-llms.md) for LLM depth.

---

## Python packaging & `uv`

- **[C-HATCH-PKG]** Hatchling can't find `src/` — install fails with "Unable to determine
  which files to ship."
  → Add to `pyproject.toml`: `[tool.hatch.build.targets.wheel]` / `packages = ["src"]`.

- **[C-MULTIPART]** FastAPI form / file upload 500s with "python-multipart not installed."
  → Add `python-multipart` to `dependencies` whenever the app accepts uploads or form posts.

- **[C-UV-DEV]** `uv run` ignores dev deps in `[project.optional-dependencies].dev`.
  → Run tests with `uv run --extra dev pytest`.

## Config & environment

- **[C-ENV-EXTRA]** pydantic-settings crashes on unknown env vars.
  → `model_config = SettingsConfigDict(..., extra="ignore")`.

- **[C-ENV-STRIP]** Inline `#` comments leak into env values: `PROVIDER=stub  # default` is
  read as the literal `"stub  # default"`.
  → Strip in a resolver property: `value.split("#")[0].strip()`. Never trust the raw value.

- **[C-PORT-8001]** Port 8000 collides with other local servers/proxies.
  → Default dev port is **8001** for every recipe; keep it configurable via env.

- **[C-HEALTH-PROVIDER]** A bare `{"status":"ok"}` health check can't tell you whether stub
  mode is active from the outside.
  → `/health` returns `llm_provider` and `stub_mode` so you can verify offline mode by curl.

- **[C-SECRET]** Secrets logged by accident.
  → Use `pydantic.SecretStr` for every key; record only a boolean in the session report —
  never the value. See [secret-hygiene.md](secret-hygiene.md).

## Databases — PostgreSQL / Alembic

- **[C-DB-SAME-AS-PROD]** SQLite tests are a lie — passing on `sqlite+aiosqlite` proves
  nothing about Postgres migrations, JSON columns, or async drivers. A
  [non-negotiable](non-negotiables.md).
  → Test against the **production driver**; the recipe `conftest.py` must not swap engines.

- **[C-ALEMBIC]** A missing `alembic/script.py.mako` makes `revision --autogenerate` fail
  cryptically.
  → Ship `script.py.mako`; the Phase-1 gate is `revision` → `upgrade head` → `current`, run
  and confirmed (not assumed).

## Databases — DuckDB (analytics / local-first)

- **[C-DUCKDB-RECIPE]** DuckDB is not a Postgres recipe with the URL swapped — reusing it
  means rewriting `db/`, dropping Alembic, editing `pyproject.toml` (it burned ~30% of one
  Iteration 0).
  → Use the `python-fastapi-duckdb` recipe.

- **[C-DUCKDB-VIEW]** DuckDB views are connection-scoped — a `CREATE VIEW` is gone after a
  server restart even though the file and the `datasets` row remain ("table or view not
  found").
  → Persist data with `CREATE OR REPLACE TABLE` (not a view), or re-create views at startup
  in the FastAPI `lifespan`. The DuckDB recipe uses persistent tables.

- **[C-DB-DIRNAME]** `os.makedirs(dirname(path))` crashes on a bare filename
  (`os.path.dirname("x.duckdb")` → `""` → `FileNotFoundError`).
  → Guard: `if dirname: os.makedirs(dirname, exist_ok=True)`.

- **[C-EXCEL-TMP]** Excel ingest via an adjacent temp CSV leaks files the view still
  references.
  → Use `tempfile.mkdtemp()` or convert to Parquet in memory.

## LLM providers (Gemini)

- **[C-LLM-SDK]** `google-generativeai` is deprecated (raises `FutureWarning`, unmaintained).
  → Use **`google-genai`** (`from google import genai`):
  `client = genai.Client(api_key=key); client.models.generate_content(...)`.

- **[C-LLM-FENCE]** Gemini wraps JSON in ```` ```json ```` fences even when told "JSON only."
  → Strip the opening/closing fence lines in `complete()` before `json.loads`.

- **[C-LLM-MODEL]** Model names go stale (`gemini-1.5-flash`, `gemini-2.0-flash` were
  deprecated / unavailable to new keys).
  → Default to **`gemini-2.5-flash`**; keep the model in config, never hardcoded.

- **[C-STUB]** The offline gate must never call a real model — a green stub run that secretly
  hit the network burns keys and lies about being offline.
  → Default `…_LLM_PROVIDER=stub`; add a hard `ALLOW_MODEL_REQUESTS=False` guard in test
  `conftest.py`.

- **[C-STUB-BANNER]** A human viewer can mistake stub output for real AI output.
  → Every UI page shows a visible banner while the provider is stubbed.

## Frontend (Next.js)

- **[C-MD-RENDER]** A GFM table dropped into `<pre>` shows literal `|` and `---`.
  → Render with `react-markdown` (+ `remark-gfm`, with `table`/`th`/`td` overrides), not `<pre>`.

- **[C-PLOTLY-SSR]** `react-plotly.js` needs `window` and breaks SSR.
  → `dynamic(() => import('react-plotly.js'), { ssr: false })`.

- **[C-SESSION-SCOPE]** Hardcoded `session_id: 'default'` makes every browser tab share one
  conversation.
  → Generate a per-tab id once: `crypto.randomUUID()` in a `useRef`/`useState` initialiser,
  with a `Math.random` fallback for non-secure contexts.

- **[C-API-URL]** `NEXT_PUBLIC_API_URL` is the only backend-URL env the browser can read.
  → Fall back to `http://localhost:8001` for local dev; never hardcode a deployed URL.

## Layout, docs & delivery

- **[C-LAYOUT]** Repo root *is* the project — no `app/` nesting. All application code in
  `src/`, tests in `tests/` at the root. See [layout.md](../layout.md).

- **[C-README]** The README is written in Iteration 0, not deferred — a repo whose README
  never gets updated leaves a cloner unable to run it (a "docs must be true"
  [non-negotiable](non-negotiables.md)). Iteration 0's deliverable includes a working quickstart.

- **[C-COPY-PASTE]** Non-coders need copy-paste commands, not instructions like "create a
  `.env` with `KEY=…`."
  → Give the exact command, what success looks like, what to do on failure. The executor
  creates `.env` from `.env.example` and prints a one-line "edit this, replace `your-key-here`."

- **[C-GIT-ADD]** `git add -A` sweeps in stray files (`data/`, `.venv`).
  → Stage specific paths only. See [git-and-delivery.md](git-and-delivery.md).
