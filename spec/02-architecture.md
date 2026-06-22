# Architecture

> **Boilerplate status:** Filled in by the tech-designer sub-agent after the product spec is approved.

---

## System Overview

<!-- FILL IN: One paragraph describing the system at a high level. Who/what interacts with it? -->

## Component Map

<!-- FILL IN: List the major components and what each does. -->

```
[Component A]
    ↓
[Component B]   ←→   [External Service]
    ↓
[Component C]
```

## Layers

<!-- FILL IN: Describe the layers of the system (e.g., API → Agent Loop → Tools → Storage). -->

| Layer | Responsibility |
|-------|----------------|
| <!-- layer --> | <!-- responsibility --> |

## Data Flow

<!-- FILL IN: Walk through the main data flow from trigger to output. -->

1. Trigger: <!-- how does the agent start? (cron, webhook, user input, etc.) -->
2. <!-- step 2 -->
3. <!-- step 3 -->
4. Output: <!-- what does the agent produce? -->

## External Dependencies

<!-- FILL IN: APIs, services, databases the agent depends on. -->

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| <!-- name --> | <!-- what it does --> | <!-- what happens if it's down --> |

## Deployment Model

<!-- FILL IN: How does this run? (local script, cloud function, long-running service, etc.) -->
