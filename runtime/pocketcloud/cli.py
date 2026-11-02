from __future__ import annotations

import argparse
import fcntl
import logging
import os
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Iterator

from alembic import command
from alembic.config import Config

from pocketcloud.config import Settings, load_settings, prepare_data_dir, require_unprivileged, secure_private_file
from pocketcloud.db import create_sqlite_engine, initialize_sqlite_file, make_session_factory
from pocketcloud.jobs import reconcile_interrupted_jobs
from pocketcloud.logging_setup import configure_logging


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def runtime_lock(settings: Settings) -> Iterator[None]:
    require_unprivileged()
    prepare_data_dir(settings.data_dir)
    lock_path = settings.data_dir / ".runtime.lock"
    secure_private_file(lock_path)
    flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another PocketCloud runtime already owns this data directory") from exc
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _alembic_config(database_url: str) -> Config:
    config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPOSITORY_ROOT / "runtime" / "pocketcloud" / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def initialize_runtime(settings: Settings) -> None:
    require_unprivileged()
    prepare_data_dir(settings.data_dir)
    secure_private_file(settings.database_path)
    os.environ["POCKETCLOUD_DATABASE_URL"] = settings.database_url
    os.environ["POCKETCLOUD_MAX_DATABASE_BYTES"] = str(settings.max_database_bytes)
    command.upgrade(_alembic_config(settings.database_url), "head")
    engine = create_sqlite_engine(settings.database_url, settings.max_database_bytes)
    initialize_sqlite_file(engine, settings.database_path)
    factory = make_session_factory(engine)
    recovered = reconcile_interrupted_jobs(factory)
    engine.dispose()
    if recovered:
        logging.getLogger("pocketcloud.lifecycle").warning(
            "interrupted_jobs_quarantined", extra={"diagnostic_code": str(recovered)}
        )


def main() -> None:
    parser = argparse.ArgumentParser(prog="pocketcloud", description="PocketCloud rootless local runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db", help="apply local SQLite schema migrations")
    serve = subparsers.add_parser("serve", help="start the local runtime on loopback")
    serve.add_argument("--host", choices=("127.0.0.1", "::1", "localhost"), default="127.0.0.1")
    serve.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    configure_logging()
    settings = load_settings()
    if args.command == "init-db":
        with runtime_lock(settings):
            initialize_runtime(settings)
        configure_logging()
        return

    if args.port is not None:
        if not 1024 <= args.port <= 65535:
            parser.error("--port must be between 1024 and 65535")
        settings = replace(settings, host=args.host, port=args.port)
    else:
        settings = replace(settings, host=args.host)

    with runtime_lock(settings):
        initialize_runtime(settings)
        configure_logging()
        logging.getLogger("pocketcloud.lifecycle").info(
            "runtime_starting", extra={"component": "lifecycle", "diagnostic_code": "loopback_only"}
        )
        from pocketcloud.api import create_app
        import uvicorn

        app = create_app(settings=settings)
        uvicorn.run(app, host=settings.host, port=settings.port, access_log=False, log_config=None)
