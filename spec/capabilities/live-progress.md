# Capability: Query Timer + Live Progress Bar (C22)

## What It Does
Shows an elapsed timer and a Step N/M progress bar while a run executes, polled from the server.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| current run state | JSON | `GET /runs/current` | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| progress UI | UI | conversation card |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| `GET /runs/current` | poll ~1/s | always 200; `status:"idle"` when none |

## Business Rules
- `execute_action` writes `iteration_count` to the DB each step; `/runs/current` returns `{run_id,status,iteration_count,max_iterations}`.
- The bar uses `role="progressbar"` + `aria-valuenow`; shows "Checking…" during clarification pre-flight.

## Success Criteria
- [ ] During a multi-iteration run, `GET /runs/current` returns an increasing `iteration_count`.
- [ ] The UI progress bar advances and the elapsed timer counts up; it resets to idle after completion.
