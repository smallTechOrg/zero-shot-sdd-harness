# Capability 02 — Data Chat

## What It Does

Accepts a plain-English question from the user, runs a ReAct (Reason + Act + Observe) loop powered by Google Gemini against the session's in-memory pandas DataFrame, and returns a grounded answer with a full reasoning trace. The agent iterates up to 10 times; if it cannot reach a definitive answer within 10 iterations it synthesizes the best-effort answer from what it has observed so far.

## Inputs

| Input | Source | Constraints |
|-------|--------|-------------|
| `session_id` | URL path parameter | Must reference an existing session with a live DataFrame in memory |
| `question` | JSON body field | Non-empty string, max 2000 characters |
| Conversation history | SQLite `messages` table | Prior user + assistant messages for the session (for context) |
| DataFrame | In-memory process cache | The pandas DataFrame parsed during file upload |

## Outputs

| Output | Destination | Description |
|--------|-------------|-------------|
| Answer text | HTTP `200` response body (`answer` field) | Plain-English answer grounded in the actual data |
| Reasoning trace | HTTP `200` response body (`reasoning_trace` field) | Ordered list of `{type, content}` steps: `"think"`, `"action"`, `"observe"` |
| `iteration_count` | HTTP `200` response body | Number of ReAct loop iterations used |
| User message record | SQLite `messages` table | `role = "user"`, `content = question` |
| Assistant message record | SQLite `messages` table | `role = "assistant"`, `content = answer`, `reasoning_trace`, `iteration_count` |

## ReAct Loop Architecture

The agent follows the **ReAct** pattern (per engineering Rule #9). Each iteration is one of:

- **THINK** — Gemini reasons about what operation it needs to perform next. Not executed; logged in trace.
- **ACTION** — Gemini outputs a pandas expression (string) to execute against the DataFrame.
- **OBSERVE** — The pandas Executor Tool runs the expression and feeds the string result back to Gemini.

The loop terminates when Gemini outputs a **FINAL ANSWER** token or after 10 iterations.

### Prompt Structure (sent to Gemini each iteration)

```
System: You are a data analyst assistant. You have access to a pandas DataFrame called `df`.
        DataFrame schema: {column_names_and_dtypes}
        First 5 rows of data: {df.head(5).to_string()}
        
        To answer questions, use the ReAct pattern:
        - THINK: reason about what to do next
        - ACTION: write a single pandas expression (no assignment, must return a value)
        - OBSERVE: you will receive the result of the expression
        - Repeat until you can state: FINAL ANSWER: {your answer here}
        
        Rules:
        - Only use pandas operations. Do not use exec(), eval(), or any import statements.
        - Limit your ACTION to a single expression that evaluates to a printable value.
        - If you reach a dead end, state FINAL ANSWER with the best answer you can give.

Conversation history: {prior messages, alternating user/assistant}

User question: {question}
```

### Pandas Executor Tool

The tool receives a string (the `ACTION` content), executes it in a sandboxed namespace containing only `df` and standard pandas/numpy, and returns the result as a string via `str(result)`. It catches all exceptions and returns the exception message as the observation so the agent can correct course.

Sandboxed namespace:
```python
{"df": session_dataframe, "pd": pandas, "np": numpy}
```

No `exec`, `eval`, `import`, `open`, `os`, or `subprocess` allowed. If the expression string contains any of those keywords it is rejected before execution with the observation: `"Error: operation not permitted."`.

### Loop Termination

| Condition | Behaviour |
|-----------|-----------|
| Gemini outputs `FINAL ANSWER: ...` | Extract the text after the token; end loop |
| 10 iterations reached without FINAL ANSWER | Prompt Gemini once more: "You have reached the iteration limit. Based on your observations so far, state your FINAL ANSWER." |
| Gemini API error on any iteration | Abort loop; return 503 to client |
| Executor raises an uncaught exception | Return the exception as an OBSERVE; continue loop |

## External Calls

| System | Call | Failure Handling |
|--------|------|-----------------|
| Google Gemini API | `generate_content(prompt)` per iteration | Raise `GeminiUnavailableError`; return 503 to client |
| pandas executor | Evaluate ACTION string in sandboxed namespace | Catch all exceptions; return exception string as OBSERVE |
| SQLite | `INSERT INTO messages` (×2: user + assistant) | Log error; return 500 |

## Error Cases

| Condition | HTTP Status | Client-Facing Message |
|-----------|-------------|----------------------|
| `question` missing or empty | 400 | "Question is required." |
| `question` > 2000 characters | 422 | "Question exceeds the 2000 character limit." |
| `session_id` not found in SQLite | 404 | "Session not found." |
| DataFrame not in memory (server restart) | 410 | "Session data was cleared. Please re-upload your file to continue." |
| Gemini API error or timeout | 503 | "The AI service is temporarily unavailable. Please try again." |
| Internal/unexpected error | 500 | "An unexpected error occurred. Please try again." |

## Success Criteria

- [ ] Asking "What is the maximum value in column X?" returns the correct numeric answer verifiable against the raw data.
- [ ] The `reasoning_trace` in the response contains at least one `ACTION` step and one `OBSERVE` step.
- [ ] Asking a question that requires 2+ steps (e.g., "Which product had the highest average amount per region?") returns the correct answer with multiple ACTION/OBSERVE pairs in the trace.
- [ ] If the pandas executor receives a forbidden keyword (`import`, `os`, etc.), the OBSERVE returned to the agent is the "not permitted" error message, and the agent recovers and tries a different approach.
- [ ] After 10 iterations without a FINAL ANSWER, the agent returns a best-effort answer (not an error) and `iteration_count = 10`.
- [ ] When Gemini is unreachable, the endpoint returns `503` and does NOT write an assistant message to SQLite.
- [ ] A follow-up question in the same session correctly uses prior conversation history as context.

## Dependencies

- **Capability 01 (File Upload):** A session with a live DataFrame must exist before this capability can run.
- **Capability 03 (Session Management):** Chat history is read from and written to SQLite by the session management layer.
