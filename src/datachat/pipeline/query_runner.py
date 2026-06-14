import json
import logging

from sqlalchemy.orm import Session

from datachat.db.models import QueryRow, UploadRow
from datachat.llm.client import get_llm_client
from datachat.pipeline.csv_reader import build_query_context, get_upload_path

logger = logging.getLogger(__name__)


def run_query(upload_id: str, question: str, session: Session, upload_dir: str) -> QueryRow:
    """Run a natural-language query against an uploaded CSV and persist the result."""
    upload = session.get(UploadRow, upload_id)
    if upload is None:
        raise ValueError(f"Upload not found: {upload_id}")

    file_path = get_upload_path(upload_dir, upload.filename)
    context = build_query_context(str(file_path))

    provider, is_stub = get_llm_client()
    prompt = (
        f"<node:query>\n"
        f"You are a data analyst. Answer the user's question based solely on the provided CSV data.\n\n"
        f"Dataset context:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Provide a clear, concise answer."
    )

    logger.info("Running query upload_id=%s is_stub=%s", upload_id, is_stub)
    answer = provider.generate(prompt)

    qrow = QueryRow(
        upload_id=upload_id,
        question=question,
        answer=answer,
    )
    session.add(qrow)
    session.flush()
    return qrow
