# Capability: Automatic Dataset Selection (C19)

## What It Does
A pre-flight LLM call picks which datasets to load for a question when none are explicitly specified.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | string | `/ask` | yes |
| all dataset schemas | JSON | DB | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset_ids subset | list | run + `AgentState` |
| selector_reasoning | string | `query_runs.selector_reasoning` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| LLM via `LLMClient` (`<node:select>`) | choose dataset subset | fall back to ALL datasets |

## Business Rules
- Skipped when explicit `dataset_ids` are supplied.
- On any failure, load ALL datasets; persist `selector_reasoning` regardless.
- Stub returns the first dataset id (per node-tag table).

## Success Criteria
- [ ] With two unrelated datasets and a question about one, the selector loads only the relevant dataset (real Gemini).
- [ ] A selector failure falls back to loading all datasets, not an error.
