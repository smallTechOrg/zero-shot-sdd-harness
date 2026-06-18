# Vision

## What This Agent Does

DataChat is a browser-based web application that lets users upload a CSV or JSON data file and then ask plain-English questions about it. An AI agent — built on a ReAct (Reason + Act) loop powered by Google Gemini — reads the uploaded data, generates pandas operations or SQL-style queries, executes them against the actual dataset, observes the results, and loops until it can return a definitive answer. The result is returned with a short reasoning trace so the user understands how the answer was derived. Users can ask as many follow-up questions as they like within a session without re-uploading their file.

## Who Uses It

**Primary user:** A non-technical or semi-technical analyst, researcher, or business stakeholder who has a data file and wants quick answers without writing code. They are comfortable with a chat interface but cannot or do not want to run Python or SQL themselves.

Their goal: upload a file once, ask several questions ("What is the average sales amount by region?", "Which product had the highest return rate?"), and get accurate, explainable answers in seconds.

## Core Problem Being Solved

Extracting insights from a CSV or JSON file today requires either writing code (Python/pandas, SQL) or importing data into a BI tool — both of which require technical skill and setup time. DataChat removes that barrier: the user uploads a file, types a question in plain English, and gets a grounded answer backed by actual query execution against their data. The agent does not hallucinate numbers — it runs real computations and shows its work.

## Success Criteria

- [ ] A user can upload a CSV or JSON file (up to 50 MB) and receive a confirmation that it was parsed successfully within 5 seconds.
- [ ] A user can ask a factual question about their data (e.g., "What is the max value in column X?") and receive a correct answer grounded in the actual data within 30 seconds.
- [ ] The agent completes its ReAct loop in 10 iterations or fewer for 95% of questions.
- [ ] Chat history within a session persists across page refreshes (stored in SQLite).
- [ ] All error states (unsupported file type, file too large, unparseable file, Gemini API failure) are surfaced to the user with a clear, actionable message.

## What This Agent Does NOT Do (Out of Scope)

- **No dashboards or visualizations** — text answers only in v0.1.
- **No automated insights** — the agent only responds to explicit user questions.
- **No multi-user authentication** — single-user, no login, no accounts in v0.1.
- **No multi-file uploads per session** — one active file per session.
- **No export or download of results** — answers are displayed in the chat UI only.
- **No file formats beyond CSV and JSON** — Excel, Parquet, Avro, etc. are out of scope.
- **No scheduled or background runs** — the agent is triggered exclusively by user chat messages.
- **No data editing or transformation** — the agent reads data; it does not mutate the uploaded file.

## Key Constraints

| Constraint | Detail |
|------------|--------|
| LLM provider | Google Gemini only (user supplies API key via environment variable) |
| File size limit | 50 MB per upload |
| Supported formats | CSV and JSON only |
| ReAct loop cap | Maximum 10 iterations per question; best-effort answer if cap is reached |
| No auth | v0.1 is single-user with no authentication layer |
| Latency target | Final answer delivered within 30 seconds for typical questions |
| Storage | SQLite for session metadata and chat history; no external database |

## Phases of Development

| Phase | Description | Success Gate |
|-------|-------------|--------------|
| 1 — Core Upload | File upload endpoint, format validation, parsing into in-memory pandas DataFrame, session record written to SQLite | Upload a 10 MB CSV; confirm DataFrame shape is returned and session is persisted |
| 2 — ReAct Agent | Gemini-powered ReAct loop that takes a user question + DataFrame, generates and executes pandas operations, returns answer + reasoning trace | Ask "What is the average of column X?" and receive a correct numeric answer with trace |
| 3 — Chat UI | React frontend with file upload widget and chat interface wired to the backend | Full end-to-end: upload file in browser, ask 3 follow-up questions, see correct answers |
| 4 — Session Persistence | Chat history persisted to SQLite; session survives page refresh | Refresh the browser mid-conversation; prior messages still visible |
