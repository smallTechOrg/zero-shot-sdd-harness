# Guardrails

**Category:** Safety & Compliance  
**Status:** Extended

## Intent

Gate every request (input guardrail) and every response (output guardrail) through safety and policy checks, independent of the agent logic, so violations are caught uniformly regardless of which agent path runs.

## When to use

- Any production agent — guardrails are not optional in deployed systems
- When regulatory, compliance, or safety requirements apply to the domain (financial advice, medical information, legal guidance, PII handling)
- When users can provide arbitrary input (the agent must not act on prompt injection, jailbreaks, or malicious instructions embedded in tool results)
- When generated output must meet content policy, accuracy, or format constraints before delivery

## How it works

Guardrails are always-on middleware that run before and after the agent, separate from agent logic:

```
User input
     │
     ▼
[Input guardrail]
  ├── safety check (harmful intent, prompt injection)
  ├── authorization check (does this user have permission?)
  ├── schema validation (is the input well-formed?)
  └──(pass / block / sanitize)
     │
     ▼
Agent (ReAct loop, tool calls, etc.)
     │
     ▼
[Output guardrail]
  ├── PII detection and redaction
  ├── toxicity / harmful content check
  ├── factual consistency check (output contradicts retrieved context?)
  ├── format validation (expected JSON schema, required fields present?)
  └──(pass / redact / block / request regeneration)
     │
     ▼
Response to user
```

## Input guardrail checks

| Check | Description | Action on failure |
|---|---|---|
| Safety classification | Detect requests for harmful, illegal, or policy-violating content | Block with explanation |
| Prompt injection detection | Detect embedded instructions in user input that try to override agent behaviour | Sanitize or block |
| Authorization | Verify the user has permission to perform this action | Block with 403 |
| Rate limiting | Prevent abuse via excessive requests | Block with 429 |
| Schema validation | Confirm required fields are present and correctly typed | Return 400 with field errors |

## Output guardrail checks

| Check | Description | Action on failure |
|---|---|---|
| PII redaction | Remove names, emails, phone numbers, SSNs, credit card numbers | Redact before returning |
| Toxicity / safety | Flag or block harmful, offensive, or discriminatory content | Block or regenerate |
| Factual consistency | Verify output is consistent with retrieved context (RAG) | Regenerate with stronger grounding instruction |
| Format validation | Verify output matches expected schema | Regenerate with formatting instruction |

## Variants

| Variant | Description |
|---|---|
| **Hard block** | Reject the request entirely if a check fails |
| **Soft sanitize** | Modify the input/output to remove the offending content and proceed |
| **Regenerate** | Reject the generated output and request another generation (with stronger constraints) |
| **Human review queue** | Flag for async human review; return a "under review" response to the user |

## Related patterns

- [13-router.md](13-router.md) — guardrails run before the router; the router does not re-check what guardrails already vetted
- [15-human-in-the-loop.md](15-human-in-the-loop.md) — the human review queue variant is a HITL integration
- [23-constitutional-ai.md](23-constitutional-ai.md) — a more nuanced form of output guardrail using principle-based self-evaluation
- [22-observability.md](22-observability.md) — every guardrail decision (pass/fail) should be traced

## Implementation notes

- Guardrails should be stateless and fast. Do not put business logic in guardrails.
- Implement guardrails as middleware (FastAPI middleware, LangChain callbacks, or an equivalent) so they apply to every request without being explicitly called in each handler.
- External guardrail services (AWS Bedrock Guardrails, NVIDIA NeMo Guardrails, Guardrails AI) offer pre-built classifiers. Evaluate before building custom.
- Log every guardrail trigger with: timestamp, check name, severity, input excerpt (truncated), and whether the request was blocked or allowed. These logs are your compliance audit trail.
- Prompt injection in **tool results** is a frequently overlooked attack surface. A malicious document retrieved by RAG or a crafted API response can inject instructions. Apply the same injection detection to tool outputs before they enter the LLM's context.
