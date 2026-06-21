# Event-Driven Agent

**Category:** Orchestration  
**Status:** Extended

## Intent

Trigger agent runs in response to external events — a new message, a database change, a webhook, a scheduled time — rather than direct user invocation. The agent is reactive to its environment.

## When to use

- Agents that monitor a system and act when conditions are met (price alert, fraud detection, anomaly detection)
- Workflow automation triggered by external events (PR opened, payment received, email arrived)
- Scheduled processing (daily report, nightly data sync, weekly digest)
- Pipelines where one agent's output triggers another agent's input

## How it works

```
Event source
  (DB trigger, webhook, message queue, cron schedule, API poll)
     │
     ▼
Event broker / queue
  (prevents event loss on agent downtime; decouples source from agent)
     │
     ▼
Agent trigger handler
  (consumes event, creates agent run record, dispatches to agent)
     │
     ▼
Agent run
  (standard ReAct loop; event payload is the initial context in AgentState)
     │
     ▼
Result publication
  (write to DB, send notification, post to downstream queue, call webhook)
```

## Event source types

| Source | Example | Pattern |
|---|---|---|
| **Webhook** | GitHub push event, Stripe payment event | HTTP endpoint that enqueues the event |
| **Message queue** | SQS, RabbitMQ, Kafka | Consumer process polling the queue |
| **Database trigger** | New row inserted in `orders` table | DB trigger → queue, or polling query |
| **Cron schedule** | Daily at 09:00 UTC | Cron job or cloud scheduler (AWS EventBridge, Cloud Scheduler) |
| **API poll** | Check every 5 minutes for new items | Scheduled polling task |
| **File watch** | New file in S3 bucket | Storage event notification |

## Scheduling variants

### Cron-triggered agent

```
Cron scheduler ──► trigger endpoint ──► agent run
                                        (processes all pending items since last run)
```

Use idempotency keys — if the cron fires twice, the second run should not duplicate work.

### Reactive / push-triggered agent

```
Event source ──► queue ──► worker process ──► agent run per event
```

Scale the worker process horizontally to handle high event volume. Each event creates an independent agent run.

## Key components

1. **Event schema** — define the exact fields in each event type before writing the trigger handler
2. **Event broker** — durable queue (SQS, RabbitMQ) or table in DB; prevents event loss on agent downtime
3. **Trigger handler** — validates the event, creates a run record, enqueues the agent task
4. **Idempotency key** — a unique identifier per event that prevents duplicate processing on retry
5. **Dead letter queue** — events that fail after N retries are moved here for manual inspection
6. **Result publisher** — sends output to downstream systems (webhook callback, DB write, notification)

## Related patterns

- [01-react-loop.md](01-react-loop.md) — each triggered run is a standard ReAct loop
- [19-checkpoint-resume.md](19-checkpoint-resume.md) — long-running event-triggered agents benefit from checkpointing
- [15-human-in-the-loop.md](15-human-in-the-loop.md) — some events may require human approval before the agent acts
- [22-observability.md](22-observability.md) — trace every event from ingestion through completion; event-driven systems are notoriously hard to debug without traces

## Implementation notes

- Every event-driven agent run must have a unique `run_id` derived from or linked to the event's idempotency key. This enables deduplication and tracing.
- Design for at-least-once delivery (queue semantics). The agent must be idempotent: running it twice on the same event should produce the same result, not duplicate side effects.
- Include a `triggered_by` field in the run record: event type, event ID, and source system. Without this, tracing an unexpected action back to its trigger event is very difficult.
- Set a maximum concurrency limit on simultaneously running agent instances. Unbounded concurrency on high-volume event streams saturates DB connections and external API rate limits.
- For cron-triggered agents, record the "last successful run" timestamp in the DB, not just in the cron system. If the cron fires but the agent fails, the next run should process from the last successful timestamp, not from "now".
