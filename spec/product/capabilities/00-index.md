# Capabilities Index

## Capabilities in This Project

| # | Capability | File |
|---|-----------|------|
| 1 | Connect a dataset → create an MCP server (Parquet directory or external DB; 1:1 by URI) | [01-connect-csv.md](01-connect-csv.md) |
| 2 | Answer natural language questions via an iterative MCP tool-call ReAct loop (generic SQL) | [02-nl-query-iterative.md](02-nl-query-iterative.md) |
| 3 | Manage sessions over one or more MCP servers (create, list, delete) | [03-sessions.md](03-sessions.md) |
| 4 | Generate & serve MCP capabilities — the 5-stage sync pipeline + the JSON-RPC tools/resources/prompts surface (versioned, soft-delete) | [04-mcp-capabilities.md](04-mcp-capabilities.md) |

## Future Capabilities (deferred)

| # | Capability | Target |
|---|------------|--------|
| 4B | Granular MCP mutation methods (`tools/add\|update`, `resources/add\|update`, `prompts/add\|update`) with cascading partial-syncs | Phase B (specced in capability 4) |
| 4C | Wire the generated GET-API tools into the agent loop (hybrid consumption) | Phase B |
| 5 | Non-CSV data source types: MySQL, REST API, GraphQL | Later |
| 6 | Charts & Visualizations | Later |
| 7 | AI-written Insights / React frontend | Later |
| 8 | Multi-user / authentication | Later |

## How to Add a New Capability

Run `/spec-new-capability [description]` or ask the spec-writer. It will create a file here, update this
index, flag dependencies, and the spec-reviewer validates the fit.
