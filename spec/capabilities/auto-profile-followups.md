# Capability: Auto-Profiling + Follow-up Suggestions  *(Phase 2)*

## What It Does
On upload, computes a full per-column profile (type, min/max range, distinct count, missing-value count) and stores it; after each answer, proposes 2–3 plain-English follow-up questions.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| full CSV | file on disk | Dataset.path (profiling, local) | yes |
| schema + question + answer | json/string | Run/Dataset | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| profile | json | Dataset.profile_json |
| followups | list[string] (2–3) | Run.followups_json |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| pandas (local) | compute profile over full file | profile omitted; upload still succeeds |
| Gemini (schema-only) | suggest 2–3 follow-ups | follow-ups omitted; answer still returned |

## Business Rules
- Profiling reads the full file locally; only schema reaches the LLM for follow-ups (privacy preserved).
- Follow-ups are cheap: one small LLM call, schema + question only.

## Success Criteria
- [ ] Uploading the olist CSV yields a profile with per-column type, range, distinct, and missing counts.
- [ ] Each answered run returns 2–3 clickable follow-up questions; clicking one runs it as a new question.
