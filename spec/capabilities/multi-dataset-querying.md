# Capability: Multi-dataset Querying (C14)

## What It Does
Lets a single question reason across multiple datasets loaded together.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_ids | list | `/ask` body or C19 selector | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer over multiple frames | string | `/ask` response |

## External Calls
None beyond the ReAct loop.

## Business Rules
- `setup` loads each dataset as `df1`/`df2`/… plus `<filename_stem>` aliases; `df` is the first.
- The selector (C19) chooses the subset when datasets are not explicitly given.

## Success Criteria
- [ ] A question that joins/compares two datasets returns a correct answer referencing both (real Gemini).
- [ ] `df1` and `df2` (and stem aliases) are available in the sandbox.
