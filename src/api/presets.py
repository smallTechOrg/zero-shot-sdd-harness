import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api._common import ok
from db.models import PresetRow
from db.session import get_session
from domain.api import PresetInfo

router = APIRouter(prefix="/api")


@router.get("/presets")
def list_presets(session: Session = Depends(get_session)) -> dict:
    rows = session.execute(
        select(PresetRow).order_by(PresetRow.is_default.desc(), PresetRow.name)
    ).scalars()
    presets = [
        PresetInfo(
            preset_id=row.id,
            name=row.name,
            is_default=row.is_default,
            values=json.loads(row.values_json),
        ).model_dump()
        for row in rows
    ]
    return ok({"presets": presets})
