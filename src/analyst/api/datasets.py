from fastapi import APIRouter, Depends, Request, Response, UploadFile
from sqlalchemy.orm import Session as DBSession

from analyst.api._common import api_error
from analyst.api.sessions import _resolve_or_create_session
from analyst.config.settings import get_settings
from analyst.db.session import get_session as get_db_session
from analyst.errors import AnalystError
from analyst.services.dataset_service import add_dataset_to_session
from analyst.services.session_store import update_session

router = APIRouter()


@router.post("/datasets")
async def upload_dataset(
    request: Request,
    response: Response,
    file: UploadFile,
    db: DBSession = Depends(get_db_session),
):
    try:
        session, _, _ = _resolve_or_create_session(request, db, response)
        settings = get_settings()

        file_bytes = await file.read()
        original_filename = file.filename or "upload"

        meta = add_dataset_to_session(session, file_bytes, original_filename, settings)
        update_session(session, db)

        return meta.model_dump(mode="json")
    except AnalystError as e:
        return api_error(e.code, e.message, e.status_code)
    except Exception as e:
        return api_error("upload_failed", str(e), 500)
