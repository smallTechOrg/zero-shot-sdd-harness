# Session Report — 2026-06-25 20:44:34 — feature/data-analysis-agent-v0.1

## Goal

Reframe a "tool" from a single datasource into a NAMED multi-table **Dataset** (URI-addressed):
internal `parquet:///{name}` = a directory of related Parquet files (one CSV → one table), or external
`postgresql://…`. Tool canonical name = dataset name; one capability per table. Keep the AI-agent core
unchanged (LLM module, LangGraph ReAct, per-session memory, SessionPoolManager).

## Phase

Implements the approved plan `/Users/tamo/.claude/plans/jaunty-sleeping-dusk.md` (6 phases:
0 spec, 1 model/migration, 2 connector seam, 3 pool/addressing cutover, 4 API, 5 UI/golden, 6 Postgres BETA).

## Session Start State

- Branch: feature/data-analysis-agent-v0.1 (PR #57 open)
- Last commit: 535c041 phase-D: durable per-session agent memory via LangGraph SqliteSaver
- Tests: 34 passing; alembic head b8e1f0a2c3d4
- Untracked/unrelated: handbook.docx/md, screenshots/ — never staged.

## Locked decisions (from user)

1. Tool = named Dataset (URI). Internal `parquet:///{name}` (dir of parquet, 1 CSV→1 table); external `postgresql://…`.
2. Tool canonical name = dataset name; ONE capability PER TABLE.
3. Two-level addressing: `{"tool":"<dataset>","capability":"<table>","arguments":{...}}`.
4. External DBs = PostgreSQL BETA behind `DATAANALYSIS_ENABLE_EXTERNAL_DATASETS` (default off); MySQL/DocumentDB deferred.
5. Connection-check the URI on create/add-csv/sync (raise before commit). Upload asks dataset name; existing datasets accept more CSVs; sync regenerates descriptions over ALL tables.

## Design source

Ultracode workflow (9 agents): exhaustive inventory + 3-lens design panel + completeness critic.
Verified env facts: DuckDB postgres_scanner installed + loads offline; psycopg2-binary already a dep; mysql_scanner not installed.

---

## Steps Completed

- [x] Ran design workflow; approved 6-phase plan; opened this report
- [x] Phase 0: spec rewrite (13 files via a parallel workflow against a shared contract; consistency-checked: two-level `{tool,capability,arguments}` format, `parquet:///` URI, `dataset_tables`/`DatasetTableRow`, add-csv, connection_check, datasets_dir + external flag all present; polished a few "data source"→"dataset" spots)
- [x] Phase 1: `DataSourceRow` += uri/last_synced_at/connection_error + `dataset_uri` derive; new `DatasetTableRow` child (UNIQUE(dataset_id,table_name), JSON accessors); settings datasets_dir + enable_external_datasets; Alembic `c3d4e5f6a7b8` (down_revision b8e1f0a2c3d4) with Python backfill (one child/legacy row, parquet_path preserved, uri+type set). Gate: migration round-trips; model + backfill tests; **39 passed** (old pipeline still green via deprecated cols).
- [x] Phase 2: connector seam — `tools/connectors/{uri,base,parquet}.py` (DatasetURI with credential-free display(); DatasetConnector Protocol + DatasetConnectionError + get_connector factory; ParquetConnector) + shared `build_dataset_server`/`register_parquet_view`/`new_connection` in `tools/mcp/server.py` (one `query_{table}` tool per table, within-dataset JOINs). Pool untouched. Gate: 5 connector tests + **44 passed**.
- [x] Phase 3: pool + addressing cutover — `pool.py` rewritten to datasets (one server/dataset via `get_connector`, grouped `snapshot`, two-level `call_tool(session,dataset,capability,args)`, lock-safe `close`, legacy-synth fallback for child-less rows); planning grouped + two-level; execution/nodes/state/stub two-level; session.html shows capability; removed dead `build_server`/`_open_view` + old `test_csv_server.py`; `get_connector` accepts legacy `csv` alias. Gate: **38 passed** (multi-table JOIN, two-level routing, dataset-namespaced tables, memory).
- [x] Phase 4: API — upload requires dataset_name+type (parquet→`datasets_dir/{id}/{table}.parquet`, create Dataset + first table, regenerate descriptions, connection-check before commit, reject dup name); new `/add-csv` (append table, auto-suffix, re-describe, close pools); `/sync` regenerates over all tables + records sanitized connection_error; `/delete` rmtrees the dir + child rows; external URI → 501 when flag off. `descriptions.py` → `generate_dataset_descriptions` (tool + per-table caps); stub describe branch updated. Gate: 6 API tests + golden path updated; **44 passed**.
- [x] Phase 5: UI — `home.py` per-dataset view-model (name, type, credential-free `uri_display`, table count, columns, last_synced, connection_error) + external flag; `home.html` rewritten for Datasets (named-upload + type chooser, dataset cards with type/table-count/URI/error badges + Add-CSV); golden-path assertion "Datasets". Gate: **44 passed**; live smoke — named dataset + add-CSV (2 tables) + session + 2 queries (memory), 1 pool build, no errors.
- [x] Phase 6: `tools/connectors/postgres.py` — PostgresConnector (BETA): psycopg2 connect+`SELECT 1`+`information_schema` introspection (hard wall-clock timeout), DuckDB `ATTACH … READ_ONLY` + view-per-table query path, credential-scrubbing error sanitization. Gated by `get_connector` on `DATAANALYSIS_ENABLE_EXTERNAL_DATASETS`. Tests: mocked-psycopg2 (check/introspect/sanitize) + gating + a skipped live test (`external_db` marker). Gate: **49 passed, 1 skipped**.

## Prompt Log

| Time | User Message | Action Taken |
|------|-------------|--------------|
| ~20:3x | "Tool = dataset (dir of parquet OR external DB by URI); name on upload; add more CSVs; sync over all tables; connection-check on create; UI for types; tool name=dataset, one capability per table." | Ran design workflow, planned 6 phases, started Phase 0. |

- [x] README + ops: README (features/structure/stack) for datasets; `.env.example`/`Dockerfile`/`render.yaml` add `DATAANALYSIS_DATASETS_DIR` (on the persistent `/data` disk) + `DATAANALYSIS_ENABLE_EXTERNAL_DATASETS`.

## Session End State

- Branch: feature/data-analysis-agent-v0.1 (PR #57 → main). All 6 phases + spec + README/ops committed and pushed; each phase green at its gate.
- A **tool is now a named, URI-addressed Dataset** (internal `parquet:///{name}` = a directory of Parquet files, one CSV→one table; external `postgresql://…` BETA, flag-gated). Tool canonical name = dataset name; one capability per table; two-level addressing `{"tool","capability","arguments"}`; within-dataset JOINs. Upload names the dataset; add-csv appends tables; sync re-describes over all tables; connection-checked before commit; delete removes the whole dataset dir.
- New: `tools/connectors/{uri,base,parquet,postgres}.py`; `DatasetTableRow`; Alembic `c3d4e5f6a7b8`; settings `datasets_dir` + `enable_external_datasets`. AI-agent core (LLM module, ReAct loop, per-session SqliteSaver memory, SessionPoolManager) unchanged.
- Tests: `uv run pytest` = **49 passed, 1 skipped** (live Postgres, BETA). Migration round-trips; live smoke (named dataset + add-CSV → 2 tables + session + memory) passed.
- Out of scope (unchanged): Gemini-vs-OpenRouter drift; vestigial `dataset.html`/`answer.html`/`history.html` templates; MySQL/DocumentDB deferred (Mongo is non-SQL, not a drop-in); credentials stored plaintext for v0.1 BETA (never logged/displayed).
