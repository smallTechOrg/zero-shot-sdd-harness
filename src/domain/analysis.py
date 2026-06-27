from pydantic import BaseModel
from typing import Optional


class AnalysisRequest(BaseModel):
    dataset_id: str
    question: str


class AnalysisResponse(BaseModel):
    analysis_id: str
    dataset_id: str
    question: str
    answer_text: Optional[str] = None
    chart_json: Optional[str] = None
    status: str
    error: Optional[str] = None
