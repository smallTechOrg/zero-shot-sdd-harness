"""Generate dashboard insights and chart specs for a dataset using Gemini."""
import json
import logging
import re

from sqlalchemy.orm import Session

from datachat.db.models import DashboardRow, DatasetRow, DatasetUploadRow, UploadRow
from datachat.llm.client import get_llm_client
from datachat.llm.providers.base import LLMResult
from datachat.pipeline.csv_reader import build_query_context, get_upload_path

logger = logging.getLogger(__name__)

_DASHBOARD_PROMPT = """<node:dashboard>
You are a data analyst. You will be given schema and sample data from one or more CSV files.

Your task is to return a JSON object (and ONLY a JSON object — no markdown fences, no explanation) with:
1. "insights": a list of 3-5 strings, each a concise plain-English insight about the data
   (trends, patterns, anomalies, notable values, correlations)
2. "charts": a list of 2-4 chart specifications, each with:
   - "type": one of "bar", "line", "scatter", "pie", "doughnut"
   - "title": a descriptive title for the chart
   - "x_column": the column name to use for the X axis (or labels)
   - "y_column": the column name to use for the Y axis (or values)
   - "file": which filename this chart is from (use "combined" if merging across files)
   - "reasoning": one sentence on why this chart is useful for this data

Rules:
- Only use column names that actually exist in the provided data
- Choose chart types that make sense for the column types (bar for categories, line for time series, scatter for two numerics)
- For pie/doughnut, x_column = label column, y_column = value column

Dataset context:
{context}

Return only valid JSON. Example shape:
{{
  "insights": ["Revenue peaks in March", "Product A has the highest return rate"],
  "charts": [
    {{"type": "bar", "title": "Revenue by Month", "x_column": "month", "y_column": "revenue", "file": "sales.csv", "reasoning": "Shows monthly revenue trend clearly"}}
  ]
}}"""


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, stripping markdown fences if present."""
    text = text.strip()
    # Strip ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


def _build_context(uploads: list[UploadRow], upload_dir: str) -> str:
    blocks = []
    for i, upload in enumerate(uploads, 1):
        try:
            ctx = build_query_context(
                str(get_upload_path(upload_dir, upload.filename)), max_rows=10
            )
        except Exception as exc:
            ctx = f"(unreadable: {exc})"
        blocks.append(f"--- File {i}: {upload.original_filename} ---\n{ctx}")
    return "\n\n".join(blocks)


def generate_dashboard(
    dataset_id: str,
    session: Session,
    upload_dir: str,
) -> DashboardRow:
    """Generate (or regenerate) a cached dashboard for the dataset."""
    dataset = session.get(DatasetRow, dataset_id)
    if dataset is None:
        raise ValueError(f"Dataset not found: {dataset_id}")

    join_rows = (
        session.query(DatasetUploadRow)
        .filter(DatasetUploadRow.dataset_id == dataset_id)
        .all()
    )
    uploads = [session.get(UploadRow, jr.upload_id) for jr in join_rows]
    uploads = [u for u in uploads if u is not None]

    if not uploads:
        raise ValueError("Dataset has no files — add at least one CSV before generating a dashboard.")

    context = _build_context(uploads, upload_dir)
    provider, is_stub = get_llm_client()
    prompt = _DASHBOARD_PROMPT.format(context=context)

    logger.info("Generating dashboard dataset_id=%s files=%d is_stub=%s", dataset_id, len(uploads), is_stub)
    result: LLMResult = provider.generate(prompt)

    try:
        parsed = _extract_json(result.text)
        insights = parsed.get("insights", [])
        charts = parsed.get("charts", [])
    except Exception as exc:
        logger.error("Failed to parse dashboard JSON: %s\nRaw: %s", exc, result.text[:500])
        insights = ["Could not parse insights — try regenerating."]
        charts = []

    # Upsert: delete existing, insert fresh
    existing = session.get(DashboardRow, dataset_id)
    if existing:
        session.delete(existing)
        session.flush()

    row = DashboardRow(
        dataset_id=dataset_id,
        insights_json=json.dumps(insights),
        charts_json=json.dumps(charts),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=result.cost_usd,
    )
    session.add(row)
    session.flush()
    return row
