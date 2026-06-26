# Capability: Insight Generation

## What It Does

Calls Gemini to produce a 2–4 sentence plain-English insight paragraph that answers the user's question in the context of the actual query results and chart type chosen.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| `question` | string | `AgentState` | Yes |
| `rows` | `list[dict]` (up to 20 rows for prompt; statistics summary if more) | `AgentState` | Yes |
| `chart_spec` | dict (`{type, xKey, yKey, title}`) | `AgentState` | Yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| `insight` | string (plain-English paragraph, 50–500 chars) | `AgentState`, `QueryRun.insight`, JSON response body |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini API | `ChatGoogleGenerativeAI.invoke()` — plain text response | Fatal — sets `state["error"]`, routes to `handle_error` |

## Business Rules

- The prompt passes: (1) the original question, (2) up to 20 rows rendered as a compact Markdown table, and (3) the chart type chosen (e.g. "a bar chart"). If there are more than 20 rows, the prompt instead includes per-column statistics: min, max, mean for numeric columns; top-5 most frequent values for text columns.
- The model is called with `temperature=0.3` for natural prose variation.
- The system instruction directs the model to: answer the user's question directly in 2–4 sentences, cite specific values from the data, and avoid hedging language ("it appears", "it seems").
- Empty result sets: the prompt notes "no rows were returned" and the model writes a "no data found" insight.
- The insight is not validated beyond being a non-empty string. The node succeeds as long as the model returns any non-empty text.
- LangSmith auto-traces this call as a child span (via `langchain-google-genai`).

## Success Criteria

- [ ] A successful query with results returns a non-empty insight string that mentions at least one specific value from the `rows` (verified by integration test checking the insight against known fixture data).
- [ ] An empty result set returns a non-empty insight string containing the phrase "no" or "zero" (model-driven, so the test checks for substring presence rather than exact match).
- [ ] A Gemini API error (simulated by an invalid API key in a separate test) results in `status: "failed"` and a human-readable `error` field in the response — not a 500 crash.
- [ ] LangSmith shows a child trace span for `insight_generation` inside the run trace.
- [ ] The insight does not echo the raw SQL query verbatim.
