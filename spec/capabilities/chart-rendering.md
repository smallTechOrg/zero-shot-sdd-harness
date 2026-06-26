# Capability: Chart Rendering

## What It Does

Inspects the SQL query result rows and column types to deterministically choose a Recharts chart type and build a JSON spec that the frontend renders without any additional API calls.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| `rows` | `list[dict]` | `sql_execution` node via `AgentState` | Yes |
| `schema` | `list[{name, type}]` | `schema_introspection` node via `AgentState` | Yes |
| `question` | string | Original user question in `AgentState` | Yes (used as chart title) |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| `chart_spec` | JSON object (see shape below) | `AgentState`, `QueryRun.chart_spec`, JSON response body |

### `chart_spec` Shape

```json
{
  "type": "bar" | "line" | "pie" | "scatter" | "empty",
  "title": "<question truncated to 60 chars>",
  "xKey": "<column name>",
  "yKey": "<column name>",
  "data": [
    {"<xKey>": "<value>", "<yKey>": <number>},
    ...
  ],
  "message": "<optional: shown when type is 'empty'>"
}
```

For `pie` charts, `data` items have `{name: string, value: number}`.
For `scatter` charts, both `xKey` and `yKey` are numeric column names.

## External Calls

None. Chart selection is a deterministic algorithm; no LLM or external API is called.

## Business Rules

- Chart type selection algorithm (evaluated in order, first match wins):
  1. If `rows` is empty → `type: "empty"`, `message: "Query returned no rows."`
  2. If result has exactly 2 columns, one is categorical (TEXT/low cardinality) and one is numeric → `"bar"`
  3. If one column appears to be a date/time (column name contains "date", "time", "year", "month", "day" case-insensitively, or values parse as ISO dates) and one column is numeric → `"line"`
  4. If one TEXT column has ≤ 8 unique values and one numeric column → `"pie"`
  5. If two or more numeric columns → `"scatter"` (first two numeric columns used as xKey/yKey)
  6. Default → `"bar"` (first column as xKey, first numeric column as yKey; if no numeric column, both are text and bar is still used)
- Numeric values in `data` are serialized as JSON numbers (not strings).
- `chart_spec` is stored as a JSON string in `QueryRun.chart_spec` and returned as a parsed JSON object in the API response.
- `chart_selection` never sets `state["error"]` — on any edge case it falls back to the `"empty"` spec. This allows `insight_generation` to still run.
- The chart title is the original `question` truncated to 60 characters.

## Success Criteria

- [ ] A two-column (text + numeric) query result produces `type: "bar"` with `data` length equal to the row count.
- [ ] A query result with a date column and a numeric column produces `type: "line"`.
- [ ] A query result with a text column having ≤ 8 unique values and a numeric column produces `type: "pie"`.
- [ ] A query result with two numeric columns produces `type: "scatter"`.
- [ ] An empty result set produces `type: "empty"` with a `message` field and does NOT set `state["error"]`.
- [ ] The frontend renders the `chart_spec` without crashing for all four chart types (verified by unit test that mounts the `AnswerCard` component with each spec type).
