import aiosqlite
from src.config import get_settings


async def get_db_path() -> str:
    return get_settings().sqlite_path


async def create_tables_sqlite() -> None:
    db_path = get_settings().sqlite_path
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        # Tables will be created in Step 1; this call just ensures the file exists.
        await db.commit()
