from __future__ import annotations

import shutil
from pathlib import Path


class StorageLimitReached(Exception):
    pass


def database_bytes(database_path: Path) -> int:
    total = 0
    for candidate in (
        database_path,
        Path(f"{database_path}-wal"),
        Path(f"{database_path}-shm"),
    ):
        try:
            total += candidate.stat().st_size
        except FileNotFoundError:
            continue
    return total


def ensure_write_capacity(
    database_path: Path,
    *,
    estimated_write_bytes: int,
    max_database_bytes: int,
    min_free_bytes: int,
) -> None:
    """Reject new work before persistence if it could consume the configured recovery reserve."""
    if database_bytes(database_path) + estimated_write_bytes > max_database_bytes:
        raise StorageLimitReached("database_quota_reached")
    free_bytes = shutil.disk_usage(database_path.parent).free
    if free_bytes - estimated_write_bytes < min_free_bytes:
        raise StorageLimitReached("recovery_space_reserved")
