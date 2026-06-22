from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    stub_mode = request.app.state.stub_mode
    return {"status": "ok", "stub_mode": stub_mode}
