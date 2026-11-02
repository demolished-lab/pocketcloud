from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, event, pool

from pocketcloud.config import DEFAULT_MAX_DATABASE_BYTES
from pocketcloud.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
database_url = os.environ.get("POCKETCLOUD_DATABASE_URL")
max_database_bytes = int(os.environ.get("POCKETCLOUD_MAX_DATABASE_BYTES", DEFAULT_MAX_DATABASE_BYTES))
if not database_url or not database_url.startswith("sqlite:////"):
    raise RuntimeError("POCKETCLOUD_DATABASE_URL must point to a local absolute-path SQLite file")
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))


def _set_sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=10000")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=FULL")
    page_size = cursor.execute("PRAGMA page_size").fetchone()[0]
    maximum_pages = max(1, max_database_bytes // page_size)
    cursor.execute(f"PRAGMA max_page_count={maximum_pages}")
    cursor.close()


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    event.listen(connectable, "connect", _set_sqlite_pragmas)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
