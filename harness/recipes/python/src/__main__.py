import uvicorn

from src.config import get_settings
from src.db.session import init_db


async def main() -> None:
    await init_db()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.env == "development",
    )
