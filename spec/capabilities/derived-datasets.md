# Capability: Derived-dataset Persistence + Lineage + Staleness (C25)

## What It Does
Lets the agent autonomously materialize a new dataset via `save_dataset(df, name, desc)`, recording its lineage and detecting when parents change (stale) so it can be re-derived.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| df, name, desc | sandbox args | `save_dataset` | yes |
| producing run + parents | context | run | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| derived dataset | `datasets` row (origin=derived) | SQLite |
| CSV + Parquet | files | `uploads/` |
| re-derive result | JSON | `POST /datasets/{id}/re-derive` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| disk | write CSV + Parquet | step error, run continues |
| SQLite | insert derived row with `derivation_code`, `derived_from_*` | step error |

## Business Rules
- `save_dataset` records `derivation_code`, `derived_from_dataset_ids`, `derived_from_run_id`, returns a confirmation string.
- A derived dataset is **stale** when a parent changed after derivation; `/re-derive` re-runs the code vs current parents and clears stale (400 `not_derived` / 404 `parent_not_found` / 400 `re_derive_error`).
- Deleting a parent recursively deletes derived children (see [dataset-deletion-cascade.md](dataset-deletion-cascade.md)).

## Success Criteria
- [ ] A question that calls `save_dataset` creates a new `origin=derived` dataset with lineage fields populated (real Gemini).
- [ ] Changing a parent marks the child stale; `/re-derive` clears it.
- [ ] `/re-derive` on a non-derived dataset returns 400 `not_derived`.
