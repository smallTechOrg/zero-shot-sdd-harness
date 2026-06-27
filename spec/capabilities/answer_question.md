# Capability: Answer Question About a Dataset

## What It Does
Answers a single plain-English question about a previously-uploaded CSV by sending the LLM only a locally-computed data profile (schema + summary statistics + tiny example values) — never the raw rows — and returning a plain-English answer grounded in that profile.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string (uuid) | Path/body of `POST /datasets/{dataset_id}/ask` (returned by the upload capability) | yes |
| question | string | Request body; the user's natural-language question | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer | string (plain English) | API response `data.answer`, rendered in the answer panel |
| status | string (`completed` \| `failed`) | API response `data.status` |
| error | string \| null | API response `data.error` (human-readable copy on failure) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (`gemini-2.5-flash`) | One `call_model(prompt, system=...)` with question + profile only | Fatal for this request: set `error`, status `failed`, return human copy ("Could not reach the analysis model — please retry.") |
| Local filesystem | Read the stored CSV at `data/datasets/{dataset_id}.csv` and re-profile it with pandas | Fatal: if the file is missing/corrupt, set `error` ("Dataset not found or unreadable") |

## Business Rules
- **Privacy (dealbreaker):** the raw pandas DataFrame, raw CSV bytes, and any full row or full column MUST NOT appear in the LLM prompt. Only the derived **data profile** (schema + summary stats + DERIVED/grouped aggregates + ≤5 truncated example values per column — see [data.md](../data.md#entity-dataprofile-in-memory-not-persisted)) and the user's question cross the network boundary to Gemini. Richer answers come from richer LOCAL computation; only derived scalars cross.
- The profile is computed **locally** on demand from the stored CSV (schema, row count, per-column dtype, per-column summary statistics, and at most 5 example values per column). Example values are capped and truncated so no full column ever leaves the machine.
- **Group-by aggregation over ANY column, including high-cardinality categorical keys** (e.g. team names): the profile carries per-group aggregates ({sum, count, mean, ratio}) for grouping-key × numeric-column. The cap is "emit only the top-N groups **by the relevant metric**" — NOT "drop the column when it has too many distinct values." A high-cardinality key (hundreds of teams) is still answerable: it is ranked locally and the top-N groups by metric cross the boundary with truncation markers.
- **Cross-column DERIVED metrics:** ratios and combinations (e.g. sum ÷ count = a per-group average, total ÷ count) are computed **locally** and cross the boundary only as derived scalars, never as the underlying rows.
- **Multi-role entity UNIONS:** when the same entity appears across more than one column (e.g. `team1`/`team2`, with `score1`/`score2` the paired metric), local computation unions the roles into per-entity aggregates (per-entity total, count/matches, and a ratio such as goals-per-match), ranked among entities meeting a minimum count, then top-N capped. Only the derived per-entity scalars cross the boundary.
- The prompt is token-frugal: profile is serialized compactly (JSON), and the system prompt instructs the model to answer ONLY from the profile and to say so plainly when the profile is insufficient to answer (rather than fabricating row-level detail it was never given).
- Each ask is stateless with respect to prior questions in Phase 1 (no conversation memory) — every request re-profiles and answers independently. Conversation memory is deferred (see [roadmap.md](../roadmap.md#out-of-scope--deferred)).
- Exactly one Gemini call per ask; no LLM-generated code execution in Phase 1.

## Success Criteria
- [ ] Given a CSV with a numeric column, asking "what is the average of <column>?" returns an answer whose number matches the locally-computed mean (within rounding) — proving the answer is grounded in the real profile, not hallucinated.
- [ ] Asking a question whose answer depends on the data content (e.g. "which category has the highest total?") returns the category that pandas computes locally as the max.
- [ ] **High-cardinality group-by:** asking "which <category> has the highest total <numeric>?" over a fixture whose grouping key has many distinct values returns the correct top group (from the locally-computed top-N-by-metric `group_aggregates`), NOT a graceful decline that the column has too many values.
- [ ] **Cross-column derived metric:** asking a question requiring a ratio (e.g. an average per group computed as sum ÷ count) returns the locally-correct derived value, grounded in the `group_aggregates` scalars.
- [ ] **Multi-role union:** asking "which teams have the best average goals per match?" over a fixture where teams appear in two columns (`team1`/`team2` with `score1`/`score2`) returns the locally-correct ranking (highest goals-per-match among teams with a minimum number of matches — Assumed min 3), grounded in the derived per-team aggregates — not a graceful decline.
- [ ] The serialized prompt sent to Gemini does NOT contain any full data row or full column: an automated test asserts the raw-DataFrame string is absent from the prompt and only profile fields (schema + summary stats + derived/grouped aggregates + ≤5 truncated example values per column) are present.
- [ ] A request with an unknown `dataset_id` returns status `failed` with a human-readable error, not a stack trace.
