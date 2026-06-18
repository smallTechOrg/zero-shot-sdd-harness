# Capabilities Index

## Capabilities in This Project (v0.1)

| # | Capability | File |
|---|-----------|------|
| 1 | File Upload — upload a CSV or JSON file, validate, parse into a queryable DataFrame, persist session metadata | [01-file-upload.md](01-file-upload.md) |
| 2 | Data Chat — ask plain-English questions; a ReAct agent queries the DataFrame and returns a grounded answer with reasoning trace | [02-data-chat.md](02-data-chat.md) |
| 3 | Session Management — create and persist sessions, store and retrieve chat history per session | [03-session-management.md](03-session-management.md) |

## Scope Rule

Exactly 3 capabilities in v0.1. The following are explicitly deferred to future phases:
- Dashboards and visualizations
- Automated / proactive insights
- Multi-user authentication
- Multi-file uploads per session
- Export or download of results
- File formats beyond CSV and JSON

## How to Add a New Capability

Run `/spec-new-capability [description]` or ask the spec-writer directly. The spec-writer will:
1. Create a new file in this directory
2. Update this index
3. Flag any dependencies on existing capabilities
4. The spec-reviewer will validate it fits the architecture
