# Capability: Multi-file / Folder Drop (C13)

## What It Does
Lets the user drag-drop multiple files or whole folders, reading folder-level and per-file notes automatically.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| files / folder | drag-drop | browser | yes |
| `_notes`/`context`/`readme` | files in folder | folder | no |
| `<stem>.notes.txt` | file per data file | folder | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| staged upload entries | UI state | upload queue (C17) |

## External Calls
None on the client; each file later hits `POST /upload`.

## Business Rules
- Folder drop reads `_notes`/`context`/`readme` as folder-wide notes and `<stem>.notes.txt` as per-file notes.
- Non-data files are treated as notes, not datasets.

## Success Criteria
- [ ] Dropping a folder with two CSVs and a `readme` stages two datasets with the readme text applied as notes.
- [ ] A `sales.notes.txt` next to `sales.csv` attaches as that file's notes.
