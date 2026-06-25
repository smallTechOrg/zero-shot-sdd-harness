# Capability: Duplicate Detection (C10)

## What It Does
Detects re-uploads of the same file by content hash and filename, returning a resolvable 409.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file bytes | bytes | upload | yes |
| filename | string | upload | yes |
| force | bool | query | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| 409 error | JSON | `{code:"duplicate_dataset", match_type, existing_*}` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | look up `content_hash` / filename | none |

## Business Rules
- Compute sha256 of bytes; a hash match (or filename match) on an existing dataset → 409 with `match_type` + existing dataset info.
- `force=true` bypasses the check and creates a new dataset.

## Success Criteria
- [ ] Uploading identical bytes twice returns 409 `duplicate_dataset` with `match_type` and the existing dataset id.
- [ ] The same upload with `force=true` returns 200 and creates a second dataset.
