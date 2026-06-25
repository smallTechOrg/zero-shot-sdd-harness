# Capability: Dataset Deletion + Cascade (C15)

## What It Does
Deletes a dataset and cascades to its sessions, runs, on-disk files, and recursively to its derived children.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset id | string | `DELETE /datasets/{id}` | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| deletion result | JSON | `ok(...)` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | delete rows (code-enforced cascade) | 404 missing; 409 in use |
| disk | remove CSV + Parquet | log + continue |

## Business Rules
- Cascade: sessions, runs, files, AND recursively any derived dataset whose `derived_from_dataset_ids` include the deleted id (transitively).
- `DELETE /datasets` deletes all with the same cascade.
- 409 `dataset_in_use` when the rules forbid deletion.

## Success Criteria
- [ ] Deleting a dataset removes its runs, its sessions, and its CSV+Parquet files.
- [ ] Deleting a parent dataset also deletes its derived children (recursively).
- [ ] Deleting a missing id returns 404.
