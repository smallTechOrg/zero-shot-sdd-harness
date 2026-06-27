"""Settings routes — GET /settings and PATCH /settings.

Exposes four user-configurable keys via the `settings` table (SettingRow):
  llm_model              — override the LLM model string (empty -> use env/default)
  max_iterations         — max ReAct iterations (0 -> use env/default)
  price_input_per_million  — USD per 1M input tokens for cost display (empty -> N/A)
  price_output_per_million — USD per 1M output tokens for cost display (empty -> N/A)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api._common import ok
from db.models import SettingRow
from db.session import get_session

router = APIRouter()

_KEYS = ("llm_model", "max_iterations", "price_input_per_million", "price_output_per_million")


def _read_all(session: Session) -> dict[str, str | None]:
    rows = {r.key: r.value for r in session.query(SettingRow).filter(SettingRow.key.in_(_KEYS)).all()}
    return {k: rows.get(k) for k in _KEYS}


@router.get("/settings")
def get_settings_route(session: Session = Depends(get_session)) -> dict:
    return ok(_read_all(session))


class SettingsPatch(BaseModel):
    llm_model: str | None = None
    max_iterations: str | None = None
    price_input_per_million: str | None = None
    price_output_per_million: str | None = None


@router.patch("/settings")
def patch_settings(body: SettingsPatch, session: Session = Depends(get_session)) -> dict:
    # model_dump with exclude_unset=True so only fields the caller sent are updated
    updates = body.model_dump(exclude_unset=True)
    for key, val in updates.items():
        if key not in _KEYS:
            continue
        row = session.get(SettingRow, key)
        if row is None:
            row = SettingRow(key=key, value=val)
            session.add(row)
        else:
            row.value = val
    # Flush so that _read_all sees the pending writes in the same transaction
    # (autoflush=False on the session factory means we must flush explicitly).
    session.flush()
    return ok(_read_all(session))
