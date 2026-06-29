# Capability: Code Execution and Interactive Charts

## What It Does

The agent executes LLM-generated Python/pandas code in a restricted server-side sandbox and captures the result (a scalar value, a summary string, or a Plotly figure). The result is passed to the response-formatting step which writes the prose answer. If a Plotly figure was produced, its JSON spec is returned to the frontend and rendered as an interactive chart.

## Inputs

| Input | Type | Source | Required |
|-------|------|---------|----------|
| Generated Python code | string | Output of LLM code-generation step | Yes |
| Loaded DataFrames | dict of `{filename_stem: pd.DataFrame}` | Files loaded from session temp directory | Yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| Result value | string (str/repr of `result` variable) | Passed to response-formatting step as context |
| Plotly chart spec | JSON dict (from `fig.to_json()`) or null | `chart_json` field in API response |
| Execution error message | string or null | Passed to error-handling step if exec() raises |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| Python exec() sandbox | Execute generated code in restricted namespace | Catch exception; return error message to user |

No LLM call is made in this step.

## Business Rules

### Sandbox Namespace

The exec() call runs with exactly this namespace — nothing else:

```python
{
    "dfs": {filename_stem: pd.DataFrame, ...},
    "pd": pandas,
    "np": numpy,
    "go": plotly.graph_objects,
    "px": plotly.express,
}
```

No `__builtins__` beyond the minimal set; no `import`, `open`, `os`, `sys`, `subprocess` accessible.

### Result Capture

After exec(), the sandbox namespace is inspected for:
- `result`: any value — converted to string via `str(result)` or `repr(result)` (max 2000 chars, truncated with notice if longer)
- `fig`: a Plotly Figure object — serialised to JSON via `fig.to_json()` and parsed to dict

Both may be present simultaneously (e.g. a chart plus a printed summary).

### Chart Rendering Contract

- Charts are returned as Plotly JSON specs in the `chart_json` response field
- The frontend renders them with react-plotly.js at full width, 350 px height
- Interactive: zoom, pan, hover tooltips enabled
- No PNG or static images — always Plotly JSON

### Execution Timeout

Execution is killed after 30 seconds. A timeout error message is returned to the user.

### Privacy

The exec() sandbox has access to full DataFrames (required for pandas operations). However, only `str(result)` — a summary value — is passed to the LLM for prose formatting; the LLM never receives the raw DataFrame contents.

## Error Handling

| Error Type | Handling |
|-----------|----------|
| SyntaxError in generated code | Caught; user-friendly message returned |
| Runtime exception (KeyError, ValueError, etc.) | Caught; error type + message returned |
| Execution timeout (> 30 s) | Process killed; timeout message returned |
| `fig` is not a valid Plotly Figure | Ignored; `chart_json` set to null |

## Success Criteria

- [ ] Ask "show me a bar chart of sales by region" → a Plotly bar chart appears in the chat UI; zoom and hover work in the browser
- [ ] Ask "what is the average revenue?" → prose answer contains the numeric value; `chart_json` is null
- [ ] LLM generates code with a SyntaxError → server returns a user-facing error message; HTTP status is 200 (not 500)
- [ ] Execution sandbox: attempting `import os` in generated code raises an error caught by the sandbox; server does not expose filesystem
- [ ] Execution taking > 30 seconds is killed and a timeout message is returned within 31 seconds
- [ ] `result` string longer than 2000 characters is truncated with a notice before being passed to the LLM
