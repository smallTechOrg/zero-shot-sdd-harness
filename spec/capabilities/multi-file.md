# Capability: Multi-file Joins & Compares  *(Phase 4)*

## What It Does
Lets the user pick 2+ datasets (or a folder treated as one dataset) and ask questions that join/compare across them; the agent writes pandas over multiple named DataFrames.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_ids | list[string] | request body | yes |
| question | string | request body | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer + chart + table | as Phase 1 | Run + SSE |
| run↔datasets link | rows | `run_datasets` join table |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | code-gen with multi-schema context (schemas+samples only) | retry / handle_error |
| Local sandbox | run code over multiple named frames | retry up to cap |

## Business Rules
- Sandbox namespace holds multiple named DataFrames; prompts include each file's schema + sample (no full data).
- A folder can be ingested as one logical multi-file dataset.

## Success Criteria
- [ ] Selecting two related CSVs and asking a join question produces a `merge`-based answer; the run records both datasets.
