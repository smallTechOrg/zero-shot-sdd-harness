from pydantic import BaseModel


class QuestionRequest(BaseModel):
    dataset_id: str
    text: str


class StepView(BaseModel):
    step_index: int
    language: str
    code: str
    result: dict | None = None
    error: str | None = None
    latency_ms: int = 0


class CostView(BaseModel):
    tokens_in: int
    tokens_out: int
    estimated_usd: float


class QuestionResponse(BaseModel):
    id: str
    status: str
    answer: str | None = None
    key_numbers: list[dict] | None = None
    result_table: dict | None = None
    plan: list[str] | None = None
    steps: list[StepView] = []
    cost: CostView | None = None
    cost_guard_warning: str | None = None
    error_message: str | None = None
