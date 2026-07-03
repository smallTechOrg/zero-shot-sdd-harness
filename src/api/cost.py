"""Cost endpoint: pre-flight token/cost estimate + expensive-run warning.

`POST /cost/estimate` gives the UI a heuristic estimate BEFORE running an
expensive question, so it can show a "this may be expensive" confirm above a
configurable threshold. The estimate is a heuristic (labelled as such): the
prompt size is approximated from the dataset profile the model would see.
"""
from __future__ import annotations

import json
import math

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import DatasetRow
from config.settings import get_settings
from llm.client import estimate_cost_usd
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.cost")

# ~4 characters per token is the standard rough heuristic.
_CHARS_PER_TOKEN = 4
# Fixed overhead for the generate_code prompt template + instructions.
_PROMPT_TEMPLATE_OVERHEAD_CHARS = 2000
# A generous flat estimate for the generated code + composed answer output.
_ESTIMATED_OUTPUT_TOKENS = 1200


class CostEstimateRequest(BaseModel):
    dataset_id: str
    question: str


@router.post("/cost/estimate")
def estimate(req: CostEstimateRequest, session: Session = Depends(get_session)) -> dict:
    dataset = session.get(DatasetRow, req.dataset_id)
    if dataset is None:
        raise api_error("NOT_FOUND", f"Dataset {req.dataset_id} not found", 404)

    # Approximate what the model actually sees: the schema + a few sample rows
    # (from the stored profile) + the question + template overhead. Raw rows are
    # never sent, so the profile is a faithful basis for the estimate.
    profile = {}
    if dataset.profile_json:
        try:
            profile = json.loads(dataset.profile_json)
        except (json.JSONDecodeError, TypeError):
            profile = {}
    schema = profile.get("columns", [])
    sample_rows = profile.get("sample_rows", [])

    context_chars = (
        len(json.dumps(schema, default=str))
        + len(json.dumps(sample_rows, default=str))
        + len(req.question or "")
        + _PROMPT_TEMPLATE_OVERHEAD_CHARS
    )
    estimated_input = math.ceil(context_chars / _CHARS_PER_TOKEN)
    estimated_output = _ESTIMATED_OUTPUT_TOKENS
    estimated_total = estimated_input + estimated_output

    estimated_usd = estimate_cost_usd(estimated_input, estimated_output)

    # Read the threshold live each call so a settings override takes effect.
    threshold = get_settings().cost_warn_threshold_usd
    warn = estimated_usd > threshold

    _log.info(
        "cost.estimate",
        dataset_id=req.dataset_id,
        estimated_tokens=estimated_total,
        estimated_usd=estimated_usd,
        warn=warn,
    )
    return ok(
        {
            "estimated_tokens": estimated_total,
            "estimated_input_tokens": estimated_input,
            "estimated_output_tokens": estimated_output,
            "estimated_usd": estimated_usd,
            "warn": warn,
            "threshold_usd": threshold,
        }
    )
