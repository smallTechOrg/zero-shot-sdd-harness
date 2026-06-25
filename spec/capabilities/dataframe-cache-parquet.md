# Capability: Session-scoped DataFrame Cache + Parquet (C27)

## What It Does
Caches loaded DataFrames per session (LRU, ~1GB) and pre-converts uploads to Parquet for fast loads.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_ids, session_id | list/string | `setup` | yes |
| Parquet/CSV files | files | `uploads/` | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| in-memory DataFrames | objects | cache / run-scoped dict |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| disk | read Parquet (preferred) / CSV (fallback) | fatal → handle_error |

## Business Rules
- Session runs use a session-keyed cache with LRU eviction (~1GB budget) + touch-on-hit.
- Single-turn runs use a run-scoped `_dataframes[run_id]` dict, released at finalize.
- Parquet is written at upload time (C1) and preferred on load.

## Success Criteria
- [ ] A second question in the same session reuses the cached DataFrame (no re-read), verifiable by faster setup / a cache-hit log.
- [ ] Loading prefers Parquet; a missing Parquet falls back to CSV without error.
