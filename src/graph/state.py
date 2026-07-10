"""LangGraph agent state per spec/agent.md — one design run's in-progress data."""

from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    session_id: str

    # Input
    user_prompt: str                 # this turn's NL request
    messages: list[dict]             # session history: [{role, content}] incl. prior clarification Q/A
    prior_params: dict | None        # accepted CulvertParams from the session's last completed run
    preset_values: dict              # defaults preset applied to this run

    # Understand
    in_scope: bool
    scope_message: str | None
    plan_text: str

    # Extract
    params: dict | None              # validated CulvertParams (merged)
    missing_critical: list[str]
    warnings: list[str]
    clarification_question: str | None

    # Deterministic pipeline (populated progressively)
    geometry: dict | None            # BoxGeometry
    assumptions: list[dict]          # Assumption records (value + source)
    trail: list[dict]                # CalcStep records from the engine
    analysis: dict | None            # AnalysisResult (Phase 2)
    checks: list[dict]               # CheckResult rows (Phase 2)
    fe_comparison: dict | None       # FE-vs-closed-form diff (Phase 2)
    checklist: list[dict]            # 12-item proof-check results (Phase 2)
    verdict: str | None              # Phase 2
    artefacts: list[dict]            # [{kind, filename}] as written
    suggestions: list[str]           # Phase 3

    # Accounting
    token_usage: list[dict]          # per-LLM-call {node, prompt_tokens, completion_tokens, latency_ms}

    # Step tracker (steps_json audit + SSE step events)
    steps: list[dict]                # per UI step {name, status, detail, started_at, ended_at}
    started_monotonic: float         # time.monotonic() at run start — drives elapsed_ms/duration_ms

    # Control
    status: str                      # running | needs_input | out_of_scope | completed | failed
    error: str | None
