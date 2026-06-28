# Capability: Execute Analysis Locally (Privacy Boundary)

## What It Does
Runs the LLM-generated pandas code in a restricted local subprocess against the real data file, capturing a structured result — the only place raw rows are touched.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| code | str | generate_code node | yes |
| dataset file path | str | Dataset.storage_path | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| exec_result | dict (scalar/table/chart-spec) | state (local) |
| result_summary | dict (aggregates only) | state → LLM-visible for summarize |
| persisted result | json | `queries.result_json` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| sandbox subprocess | load file → `df`, run code | capture error → one repair loop → handle_error |

## Business Rules
- Subprocess has no network access, no filesystem writes outside a temp dir, wall-clock + memory limits.
- Only this node reads raw rows; the result_summary derived for the LLM contains aggregates, not rows.
- Subprocess crash/timeout never crashes the main process.

## Success Criteria
- [ ] Generated code runs and produces a numeric/tabular result for a real CSV.
- [ ] A deliberately failing snippet is captured as an execution error and triggers the repair loop.
- [ ] The subprocess cannot make a network call (asserted in test).
