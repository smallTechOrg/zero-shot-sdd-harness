# Data Analyst Agent

Ask natural-language questions over CSV, JSON, Excel, and Parquet files. Powered by Gemini 2.5 Flash + DuckDB.

## Prerequisites

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) package manager (`brew install uv` or `pip install uv`)
- Node.js >= 20 (for the frontend)

## Quickstart (backend, stub mode — no API key needed)

```bash
# 1. Install dependencies
uv sync --extra dev

# 2. Copy env file
cp .env.example .env

# 3. Start the server
uv run uvicorn src.api.main:app --port 8001

# 4. Verify health
curl http://localhost:8001/health
# -> {"status":"ok","stub_mode":true,"llm_provider":"stub"}
```

To use live Gemini AI, set `DAA_LLM_PROVIDER=gemini` and `DAA_GEMINI_API_KEY=your-key` in `.env`.

---

# SDD Agent Harness

A spec-driven development harness for building AI agents with Claude Code.

Describe what you want to build. The harness takes it from brief to working, tested,
deployed agent — spec first, no shortcuts.

---

## How it works

```
brief → spec → phases → code → tests → deploy → reconcile ↺
```

1. **Researcher** elicits requirements and writes the phased product spec (`spec/delivery-plan.md` carries the durable phase roadmap)
2. **Planner** slices the current phase into a parallel step DAG with gate tests, written to `logs/PLAN.md`
3. **Executor** implements each step in `src/` — exactly what the spec says
4. **Reviewer** guards the goal — nothing ships without sign-off
5. **Deployer** ships it — local demo first, cloud on request
6. **Analyser** closes the loop — detects drift, routes corrections

The loop runs autonomously after one human-touch approval gate.

## Quick start

```bash
git clone https://github.com/smallTechOrg/sdd-agent-harness
cd sdd-agent-harness
# Open in Claude Code and run /build
```

## Structure

```
harness/    the method — rules, process, patterns (read this first)
spec/       the contract — the 7 phased product-spec docs (vision, architecture, data-model, api, ui, agent-graph, delivery-plan)
src/        the code — written by the executor, conforms to spec
logs/       the evidence — PLAN.md (live coordination), sessions, analysis
.claude/    Claude Code adapter — agents, skills, hooks
```

Full documentation: [harness/README.md](harness/README.md)
