from typing import Any
from pydantic import BaseModel


class ColumnInfo(BaseModel):
    name: str
    dtype: str


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    row_count: int
    col_count: int
    columns: list[ColumnInfo]
    uploaded_at: str | None = None


class AnalysisRequest(BaseModel):
    upload_id: str
    analysis_type: str
    params: dict[str, Any] = {}


class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    summary: str | None = None
    chart_json: str | None = None
    table: list[dict] | None = None
    error: str | None = None
