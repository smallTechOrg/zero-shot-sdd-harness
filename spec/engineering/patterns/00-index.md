# Agentic AI Design Patterns

Exhaustive catalog of patterns for building reliable AI agents in 2026. Patterns extracted from `spec/engineering/ai-agents.md` are marked **[core]**; all others are **[extended]**.

Patterns are organized by function. Most production agents combine 4–8 of these.

---

## Loop & Reasoning

| Pattern | File | Status |
|---|---|---|
| ReAct Loop | [01-react-loop.md](01-react-loop.md) | **[core]** |
| Plan-and-Execute | [06-plan-and-execute.md](06-plan-and-execute.md) | [extended] |
| Chain of Thought | [07-chain-of-thought.md](07-chain-of-thought.md) | [extended] |
| Tree of Thoughts | [08-tree-of-thoughts.md](08-tree-of-thoughts.md) | [extended] |
| Prompt Chaining | [21-prompt-chaining.md](21-prompt-chaining.md) | [extended] |

## Tool & Resource Access

| Pattern | File | Status |
|---|---|---|
| Tool Registry | [02-tool-registry.md](02-tool-registry.md) | **[core]** |
| Code Interpreter | [20-code-interpreter.md](20-code-interpreter.md) | [extended] |
| Retrieval Augmented Generation (RAG) | [10-rag.md](10-rag.md) | [extended] |
| Context Window Management | [24-context-window-management.md](24-context-window-management.md) | [extended] |

## Orchestration

| Pattern | File | Status |
|---|---|---|
| Execution Plan | [03-execution-plan.md](03-execution-plan.md) | **[core]** |
| Sub-agent as Tool | [04-sub-agent-as-tool.md](04-sub-agent-as-tool.md) | **[core]** |
| Orchestrator-Worker | [16-orchestrator-worker.md](16-orchestrator-worker.md) | [extended] |
| Router / Intent Classifier | [13-router.md](13-router.md) | [extended] |
| Event-Driven Agent | [18-event-driven-agent.md](18-event-driven-agent.md) | [extended] |

## Memory

| Pattern | File | Status |
|---|---|---|
| Memory Patterns | [09-memory-patterns.md](09-memory-patterns.md) | [extended] |
| Checkpoint / Resume | [19-checkpoint-resume.md](19-checkpoint-resume.md) | [extended] |

## Evaluation & Quality

| Pattern | File | Status |
|---|---|---|
| Self-Correction | [05-self-correction.md](05-self-correction.md) | **[core]** |
| LLM-as-Judge | [11-llm-as-judge.md](11-llm-as-judge.md) | [extended] |
| Self-Consistency / Best-of-N | [12-self-consistency.md](12-self-consistency.md) | [extended] |
| Multi-agent Debate | [17-multi-agent-debate.md](17-multi-agent-debate.md) | [extended] |

## Safety & Compliance

| Pattern | File | Status |
|---|---|---|
| Guardrails | [14-guardrails.md](14-guardrails.md) | [extended] |
| Human-in-the-Loop | [15-human-in-the-loop.md](15-human-in-the-loop.md) | [extended] |
| Constitutional AI | [23-constitutional-ai.md](23-constitutional-ai.md) | [extended] |

## Observability

| Pattern | File | Status |
|---|---|---|
| Observability / Tracing | [22-observability.md](22-observability.md) | [extended] |

---

## How to read these files

Each pattern file covers:
- **Intent** — one-sentence description
- **When to use** — conditions that call for this pattern
- **How it works** — mechanics and diagram where useful
- **Key components** — named parts to spec before coding
- **Variants** — notable specializations
- **Related patterns** — what to combine with
- **Implementation notes** — gotchas and non-negotiables
