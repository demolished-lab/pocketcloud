from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine

_MIGRATION_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def _migration_files(directory: Path) -> list[tuple[int, Path]]:
    entries: list[tuple[int, Path]] = []
    for path in directory.glob("*.sql"):
        match = _MIGRATION_NAME.fullmatch(path.name)
        if not match:
            raise RuntimeError("migration directory contains an invalid filename")
        entries.append((int(match.group(1)), path))
    entries.sort(key=lambda item: item[0])
    versions = [version for version, _ in entries]
    if len(set(versions)) != len(versions) or versions != list(range(1, len(versions) + 1)):
        raise RuntimeError("migration versions must be unique and contiguous from 0001")
    return entries


def _statements(source: str) -> list[str]:
    statements: list[str] = []
    pending = ""
    for line in source.splitlines():
        pending += line + "\n"
        if sqlite3.complete_statement(pending):
            if pending.strip():
                statements.append(pending.strip())
            pending = ""
    if pending.strip():
        raise RuntimeError("migration contains an incomplete SQL statement")
    return statements


def apply_migrations(engine: Engine, directory: Path) -> int:
    """Apply immutable, checksummed SQLite migrations in one transaction each."""
    applied_count = 0
    entries = _migration_files(directory)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, checksum_sha256 TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        rows = connection.exec_driver_sql(
            "SELECT version, checksum_sha256 FROM schema_migrations ORDER BY version"
        ).all()
        applied = {int(row[0]): str(row[1]) for row in rows}

        for version, path in entries:
            source_bytes = path.read_bytes()
            checksum = hashlib.sha256(source_bytes).hexdigest()
            if version in applied:
                if applied[version] != checksum:
                    raise RuntimeError("an applied migration file changed; refusing to alter schema history")
                continue
            if version != len(applied) + 1:
                raise RuntimeError("schema migration history has a gap; refusing to skip a migration")

            source = source_bytes.decode("utf-8")
            for statement in _statements(source):
                connection.exec_driver_sql(statement)
            applied_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            connection.exec_driver_sql(
                "INSERT INTO schema_migrations(version, checksum_sha256, applied_at) VALUES (?, ?, ?)",
                (version, checksum, applied_at),
            )
            applied[version] = checksum
            applied_count += 1

        if applied and max(applied) > len(entries):
            raise RuntimeError("database schema is newer than this PocketCloud runtime")
    return applied_count
