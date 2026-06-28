"""Structured (stdout JSON) observability for the analyst pipeline.

Two first-class signals, both always on (Phase-1 deliverable):

* ``log_llm_call`` — model, the FULL prompt + system text, the output, real
  prompt/completion token counts, latency, derived cost. The full prompt is
  logged on purpose so the privacy test can assert no raw data row value ever
  reaches an LLM input (schema + bounded aggregates only).
* ``log_run_outcome`` — per-run status, total duration, error.

The privacy audit relies on the LLM-input being assertable: callers pass the
exact ``prompt``/``system`` strings that were sent to the model.
"""
import structlog


def configure_logging(log_level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__("logging"), log_level, 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(name: str = "agent") -> structlog.BoundLogger:
    return structlog.get_logger(name)


def log_llm_call(
    *,
    run_id: str | None,
    node: str,
    model: str,
    prompt: str,
    system: str | None,
    output: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    cost_usd: float,
) -> None:
    """Log one LLM call with the FULL prompt (privacy-auditable) + usage/cost."""
    get_logger("llm").info(
        "llm_call",
        run_id=run_id,
        node=node,
        model=model,
        # The exact text sent to the model — asserted by the privacy test.
        prompt=prompt,
        system=system or "",
        output=output,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
    )


def log_step(
    *,
    run_id: str | None,
    step: str,
    ok: bool,
    latency_ms: int,
    error: str | None = None,
) -> None:
    """Log one pipeline step outcome (plan / guard / execute / retry / phrase / chart)."""
    get_logger("graph").info(
        "step",
        run_id=run_id,
        step=step,
        ok=ok,
        latency_ms=latency_ms,
        error=error,
    )


def log_run_outcome(
    *,
    run_id: str | None,
    dataset_id: str | None,
    status: str,
    duration_ms: int,
    cost_usd: float,
    error: str | None = None,
) -> None:
    """Log a run's final outcome: status, duration, cost, error."""
    get_logger("graph").info(
        "run_outcome",
        run_id=run_id,
        dataset_id=dataset_id,
        status=status,
        duration_ms=duration_ms,
        cost_usd=cost_usd,
        error=error,
    )
