"""Question runner: create row → load dataset → invoke graph → persist.

Persists the `questions` row (answer/plan/status/warning), one `analysis_steps`
row per executed step (code + bounded result), and a `cost_records` row
(tokens summed, estimated USD via Flash price settings, model id).
"""
from __future__ import annotations

from config.settings import get_settings
from db.models import AnalysisStep, CostRecord, Dataset, Question
from db.session import create_db_session, init_db
from graph.agent import agentic_ai
from graph.state import AgentState
from observability.events import get_logger

_log = get_logger("runner")


def _estimated_usd(tokens_in: int, tokens_out: int) -> float:
    s = get_settings()
    return round(
        (tokens_in / 1_000_000) * s.price_in_per_m
        + (tokens_out / 1_000_000) * s.price_out_per_m,
        6,
    )


def run_question(question_id: str) -> str:
    """Run the agent for an existing `questions` row and persist the result."""
    init_db()
    settings = get_settings()

    # Load the question + dataset.
    with create_db_session() as session:
        question = session.get(Question, question_id)
        if question is None:
            raise ValueError(f"Question {question_id} not found")
        dataset = session.get(Dataset, question.dataset_id) if question.dataset_id else None
        if dataset is None:
            question.status = "failed"
            question.error_message = "Dataset not found for this question."
            return question_id
        dataset_id = dataset.id
        csv_path = dataset.path
        schema = dataset.schema_json or []
        sample_rows = dataset.sample_rows_json or []
        question_text = question.text

    _log.info("question_received", question_id=question_id, dataset_id=dataset_id)

    initial: AgentState = {
        "run_id": question_id,
        "question_id": question_id,
        "dataset_id": dataset_id,
        "csv_path": csv_path,
        "schema": schema,
        "sample_rows": sample_rows,
        "question_text": question_text,
        "tokens_in": 0,
        "tokens_out": 0,
        "error": None,
    }

    final = agentic_ai.invoke(initial)

    status = final.get("status", "completed")
    tokens_in = int(final.get("tokens_in", 0))
    tokens_out = int(final.get("tokens_out", 0))
    model = settings.llm_model or "gemini-2.5-flash"

    with create_db_session() as session:
        question = session.get(Question, question_id)
        question.status = status
        question.plan_json = final.get("plan")
        question.answer = final.get("answer")
        question.key_numbers_json = final.get("key_numbers")
        question.result_table_json = final.get("result_table")
        question.cost_guard_warning = final.get("cost_guard_warning")
        question.error_message = final.get("error")

        for step in final.get("steps", []):
            session.add(
                AnalysisStep(
                    question_id=question_id,
                    step_index=step.get("index", 0),
                    language=step.get("language", "sql"),
                    code=step.get("code", ""),
                    result_json=step.get("result"),
                    error=step.get("error"),
                    latency_ms=int(step.get("latency_ms", 0)),
                )
            )

        session.add(
            CostRecord(
                question_id=question_id,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                estimated_usd=_estimated_usd(tokens_in, tokens_out),
                model=model,
            )
        )

    return question_id
