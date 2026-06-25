# Capability: Token Usage Widget + Daily Stats (C18)

## What It Does
Shows model name, last-query and today's token usage/cost, and storage totals in the sidebar.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| daily stats | JSON | `GET /stats/daily` | yes |
| last run tokens | JSON | `/ask` response | yes |
| dataset totals | JSON | `GET /datasets` | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| widget render | UI | sidebar |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| `GET /stats/daily` | aggregate today's completed runs | always 200 |

## Business Rules
- `/stats/daily` aggregates over the server-local day; `context_limit` from a hard-coded model table (unknown → 128000).
- Client-side pricing table computes cost; unknown model → "N/A".
- Storage row = dataset count + total rows.

## Success Criteria
- [ ] After one real run, the widget shows non-zero Last In/Out and Today totals matching `/stats/daily`.
- [ ] An unknown model shows "N/A" cost, not a crash.
