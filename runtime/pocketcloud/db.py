from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from pocketcloud.config import secure_private_file


def create_sqlite_engine(database_url: str, max_database_bytes: int | None = None) -> Engine:
    if not database_url.startswith("sqlite:///"):
        raise ValueError("PocketCloud Stage 1 supports only a local SQLite database")

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False, "timeout": 10},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def _set_connection_pragmas(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA synchronous=FULL")
        if max_database_bytes is not None:
            page_size = cursor.execute("PRAGMA page_size").fetchone()[0]
            maximum_pages = max(1, max_database_bytes // page_size)
            cursor.execute(f"PRAGMA max_page_count={maximum_pages}")
        cursor.close()

    return engine


def initialize_sqlite_file(engine: Engine, database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    secure_private_file(database_path)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        connection.exec_driver_sql("PRAGMA synchronous=FULL")


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
    finally:
        session.close()
