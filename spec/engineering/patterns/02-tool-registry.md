# Tool Registry

**Category:** Tool & Resource Access  
**Status:** Core — required for any agent with dynamic tool access

## Intent

Store tool definitions in the application database and load them at runtime, so the agent discovers its capabilities dynamically rather than through a hardcoded list in agent code.

## When to use

- Whenever the set of tools an agent can use varies by user, session, or configuration
- When tools are added/removed without a code deployment (user uploads a file, enters an API key, connects a service)
- When multiple tool types (databases, APIs, sub-agents) need a uniform interface

## How it works

### Registration flow

```
User connects a provider
(uploads a file, provides an API endpoint, enters credentials, etc.)
         ↓
System creates a Tool record (name, type, description, config_json)
         ↓
System creates Capability records (one per action the tool exposes)
         ↓
Tool is available to any session that includes this provider
```

### Tool anatomy

Every tool has the same structure regardless of type:

```
Tool
  ├── id           — unique identifier (UUID)
  ├── name         — snake_case label shown to the LLM (e.g. "weather_api", "send_email")
  ├── type         — implementation type that determines which executor runs it
  ├── description  — one sentence shown to the LLM in the planning prompt
  ├── config_json  — type-specific runtime config (base URL, credentials ref, table name, etc.)
  └── capabilities — one or more named actions the tool exposes
        └── Capability
              ├── name              — the callable action (e.g. "get_forecast", "send", "search")
              ├── description       — shown to the LLM
              └── parameter_schema  — JSON Schema dict describing the parameters
```

Store Tool and Capability records in the application database. Do not hardcode them in agent source code.

### Tool categories

| Category | Example types | When to use |
|---|---|---|
| **Data source** | `csv_query`, `sql_query`, `vector_search`, `graphql_query` | Agent reads or queries external data |
| **External action** | `http_request`, `send_email`, `post_webhook`, `write_file` | Agent affects the outside world |
| **Compute** | `python_eval`, `shell_exec` | Agent runs calculations or scripts (sandbox required) |
| **Orchestration** | `sub_agent` | Master agent delegates to a child agent |

### Pre-loop loading

Before the ReAct loop starts, load all Tool + Capability records for the session from DB into `AgentState`:

```python
tools: list[dict]  # [{"name", "type", "config", "capabilities": [{"name", "description", "parameter_schema"}]}]
```

This makes the full tool list available on every `plan_action` call without additional DB queries.

## Key components

1. **Tool DB model** — persistent store for Tool + Capability records
2. **Registration handler** — creates Tool/Capability records on user action
3. **Pre-loop loader** — queries DB, populates `AgentState.tools`
4. **Executor dispatch** — `invoke_tool` looks up tool by `tool_name`, routes to the correct executor by `type`

## Security boundaries (non-negotiable)

| Category | Constraint |
|---|---|
| Data source | Enforce read-only at executor level. Reject any write attempt as a recoverable error. Log every rejection. |
| External action | Require explicit user opt-in in UI before the session starts for any irreversible action. Log every execution with parameters. |
| Compute | Require a sandboxed executor. Never enable by default. |

## Related patterns

- [01-react-loop.md](01-react-loop.md) — the loop that consumes the tool registry
- [04-sub-agent-as-tool.md](04-sub-agent-as-tool.md) — sub-agents registered as `Orchestration` tools
- [03-execution-plan.md](03-execution-plan.md) — execution plans reference tools by `tool_name`
- [20-code-interpreter.md](20-code-interpreter.md) — code interpreter is a `Compute` category tool

## Implementation notes

- `config_json` stores credential references (e.g. a secret name), not plaintext credentials.
- Tools for the same provider type share an executor class — only `config_json` differs between instances.
- The LLM is shown `tool_name`, `description`, and each capability's `name`, `description`, and `parameter_schema` at each `plan_action` call. The `config_json` is never sent to the LLM.
- When a user disconnects a provider, soft-delete the Tool record; it remains in `tool_call_history` for runs that already used it.
