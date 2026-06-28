from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import AnalysisStep, CostRecord, Dataset, Question
from db.session import get_session
from domain.question import CostView, QuestionRequest, QuestionResponse, StepView
from graph.runner import run_question

router = APIRouter()


def _build_payload(session: Session, question: Question) -> dict:
    steps = (
        session.execute(
            select(AnalysisStep)
            .where(AnalysisStep.question_id == question.id)
            .order_by(AnalysisStep.step_index)
        )
        .scalars()
        .all()
    )
    cost = session.execute(
        select(CostRecord).where(CostRecord.question_id == question.id)
    ).scalar_one_or_none()

    cost_view = (
        CostView(
            tokens_in=cost.tokens_in,
            tokens_out=cost.tokens_out,
            estimated_usd=cost.estimated_usd,
        )
        if cost
        else None
    )

    resp = QuestionResponse(
        id=question.id,
        status=question.status,
        answer=question.answer,
        key_numbers=question.key_numbers_json,
        result_table=question.result_table_json,
        plan=question.plan_json,
        steps=[
            StepView(
                step_index=s.step_index,
                language=s.language,
                code=s.code,
                result=s.result_json,
                error=s.error,
                latency_ms=s.latency_ms,
            )
            for s in steps
        ],
        cost=cost_view,
        cost_guard_warning=question.cost_guard_warning,
        error_message=question.error_message,
    )
    return resp.model_dump()


@router.post("/questions")
def create_question(req: QuestionRequest, session: Session = Depends(get_session)) -> dict:
    dataset = session.get(Dataset, req.dataset_id)
    if dataset is None:
        raise api_error("DATASET_NOT_FOUND", f"Dataset {req.dataset_id} not found", 404)

    question = Question(dataset_id=req.dataset_id, text=req.text, status="pending")
    session.add(question)
    session.flush()
    question_id = question.id
    session.commit()

    # ANALYSIS_FAILED is surfaced as a 200 with status:"failed" — never thrown.
    run_question(question_id)

    session.expire_all()
    question = session.get(Question, question_id)
    return ok(_build_payload(session, question))


@router.get("/questions/{question_id}")
def get_question(question_id: str, session: Session = Depends(get_session)) -> dict:
    question = session.get(Question, question_id)
    if question is None:
        raise api_error("NOT_FOUND", f"Question {question_id} not found", 404)
    return ok(_build_payload(session, question))
