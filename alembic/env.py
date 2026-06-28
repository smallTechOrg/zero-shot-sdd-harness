import os
import sys
from pathlib import Path

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make src/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.settings import get_settings
from db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override sqlalchemy.url from settings
_database_url = get_settings().database_url
config.set_main_option("sqlalchemy.url", _database_url)


def _ensure_sqlite_dir(url: str) -> None:
    """SQLite will not create a missing parent directory (e.g. data/).

    The data/ dir is gitignored and created at runtime — ensure it exists
    before the migration opens the file, so a clean checkout can upgrade.
    """
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return
    db_path = url[len(prefix):]
    if db_path in ("", ":memory:"):
        return
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


_ensure_sqlite_dir(_database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
