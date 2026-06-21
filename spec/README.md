# spec/ — the intention layer

The human-authored contract for this project. All code must match this spec; when they
disagree, spec wins — fix the code. The researcher authors it; the supervisor signs it
off. See [../harness/README.md](../harness/README.md) for the full SDD method.

```
spec/
  rules/        constraints — tech stack, code style, rule overrides
  features/     what the system should do — vision, architecture, capabilities
  patterns/     optional — reusable patterns the coding agent may apply
```

---

## rules/

Hard constraints for this project. The researcher fills these in at intake.

- [rules/tech-stack.md](rules/tech-stack.md) — language, framework, DB, deploy target
- [rules/code-style.md](rules/code-style.md) — style rules, framework gotchas

Any overrides to [harness/rules/](../harness/rules/) also live here.

## features/

What the system should be. The researcher fills these in; they are the source of truth
for product intent. Code conforms to features, never the reverse.

- [features/vision.md](features/vision.md) — purpose, goals, success criteria
- [features/architecture.md](features/architecture.md) — system design, layers, data flow
- [features/data-model.md](features/data-model.md) — data schema
- [features/api.md](features/api.md) — API surface
- [features/ui.md](features/ui.md) — UI requirements
- [features/agent-graph.md](features/agent-graph.md) — agent graph (LangGraph/etc. projects)

To add a capability: add a file to `features/`. One file = one discrete feature.

## patterns/

Lateral patterns — cross-cutting concerns that apply broadly across the system
(e.g. retry strategy, caching approach, observability conventions). Optional;
the coding agent adds these when a pattern emerges and is worth codifying.

---

## Governance

1. **Spec first** — no `src/` change without a backing spec change.
2. **One fact, one place** — never duplicate across files; cross-reference with links.
3. **`features/` = WHAT, `rules/` = HOW + constraints** — no implementation detail in features.
4. **Update spec before code** — if requirements change, spec changes first.
