# Agentic boilerplate — a spec-driven harness for Claude Code

An opinionated, lean, **Claude-Code-native harness** that builds and evolves an agentic-AI agent and keeps its
**spec and code always in sync**. The harness is the product; the `agent/` is the example it builds and
proves. Code is truth; the spec is a projection reconciled to it.

## Quickstart
```bash
make setup                                  # uv sync + the Playwright browser
printf 'APP_LLM_PROVIDER=google_genai\nAPP_LLM_MODEL=gemini-2.5-flash\nAPP_LLM_API_KEY=<your funded key>\n' > .env
make gate                                   # the proof: boots, two-turn run, judges the answer — exit 0 = done
make dev                                    # run the agent at http://localhost:8001  (form + /traces dashboard)
```

## The harness (in Claude Code)
- `/new "<idea>"` — bootstrap a new agent (spec → a proven v1).
- `/change "<intent>"` — evolve it; code + spec end reconciled.
- `/sync` — reconcile the spec from the current code (code → spec).
- `make analyze` — the reconciliation guard: every EARS criterion bound to a test, every `targets:` glob real. The pre-commit hook enforces it.

## What's here
```
agent/        the real, tested agent — a grounded assistant (retrieval · memory · guardrails+HITL · streaming)
spec/         capabilities/*.md — EARS criteria, each bound to a test ([@eval]) and to code (targets:)
tests/        the suite + the gate
.claude/      the harness — commands (/new /change /sync) · agents (spec-projector, reviewer)
.githooks/    secret-scan + spec↔code reconciliation guard
render.yaml   deploy stub (Render)
CLAUDE.md     the entry point Claude Code loads
```

## Minimal / stubbed (build along)
- **UI** — a server-rendered form (`/`) + a metrics dashboard (`/traces`: runs, cost, tokens, latency). A Next.js front-end is the documented next step.
- **Multi-agent** — `agent/multi_agent.py` scaffold (off by default).
- **Deploy** — `render.yaml` stub.

## Done means
`make gate` exits 0 — the agent booted and gave the **right** answer (a 200 with a wrong answer fails), and
`make analyze` confirms spec ↔ code reconcile. MIT licensed.
