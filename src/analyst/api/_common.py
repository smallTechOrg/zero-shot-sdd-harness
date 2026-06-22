from fastapi.responses import JSONResponse


def ok(data: dict) -> dict:
    return data


def api_error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status_code)
