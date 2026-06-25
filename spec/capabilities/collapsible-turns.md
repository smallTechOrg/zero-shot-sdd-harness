# Capability: Collapsible Conversation Turns (C32)

## What It Does
Lets the user collapse/expand individual turns (and all at once), persisted client-side.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| collapse state | sessionStorage | browser | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| collapsed/expanded UI | UI | conversation card |

## External Calls
None (client-only).

## Business Rules
- Per-turn collapse/expand + Collapse all / Expand all.
- State persisted in `sessionStorage` and restored on reload.

## Success Criteria
- [ ] Collapsing a turn hides its body; reloading the page restores the collapsed state.
- [ ] Collapse all / Expand all toggles every turn.
