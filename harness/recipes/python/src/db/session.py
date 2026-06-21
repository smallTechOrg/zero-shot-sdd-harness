from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings
from src.db.base import Base

_engine = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    global _engine, AsyncSessionLocal
    settings = get_settings()
    _engine = create_async_engine(settings.database_url, echo=False)
    AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
