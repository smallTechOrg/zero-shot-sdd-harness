import os
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from data_analyst.db.models import Base
target_metadata = Base.metadata


def get_url() -> str:
    # Check env override first
    url = os.environ.get("ANALYST_DATABASE_URL", "")
    if url:
        # Resolve relative sqlite paths
        if url.startswith("sqlite:///./"):
            rel = url[len("sqlite:///./"):]
            return f"sqlite:///{Path(rel).resolve()}"
        return url
    # Fall back to alembic.ini setting
    raw = config.get_main_option("sqlalchemy.url", "sqlite:///./data/session.db")
    if raw.startswith("sqlite:///./"):
        rel = raw[len("sqlite:///./"):]
        return f"sqlite:///{Path(rel).resolve()}"
    return raw


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = get_url()
    # Ensure data dir exists for SQLite
    import re
    m = re.match(r"sqlite:///(.+)", url)
    if m:
        Path(m.group(1)).parent.mkdir(parents=True, exist_ok=True)

    connectable = engine_from_config(
        {"sqlalchemy.url": url},
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
