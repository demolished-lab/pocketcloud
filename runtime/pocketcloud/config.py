from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MAX_DATABASE_BYTES = 64 * 1024 * 1024
DEFAULT_MIN_FREE_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Settings:
    data_dir: Path
    host: str = "127.0.0.1"
    port: int = 8765
    max_database_bytes: int = DEFAULT_MAX_DATABASE_BYTES
    min_free_bytes: int = DEFAULT_MIN_FREE_BYTES

    @property
    def database_path(self) -> Path:
        return self.data_dir / "pocketcloud.sqlite3"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"


def _positive_int(name: str, default: int, *, allow_zero: bool = False) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < (0 if allow_zero else 1):
        comparator = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {comparator}")
    return value


def _private_home_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    home = Path.home().resolve()
    if resolved == home:
        raise PermissionError("PocketCloud state must use a dedicated child directory under the user's home")
    try:
        resolved.relative_to(home)
    except ValueError as exc:
        raise PermissionError("PocketCloud state must be stored under the current user's home directory") from exc
    return resolved


def load_settings() -> Settings:
    raw_dir = os.environ.get("POCKETCLOUD_DATA_DIR")
    requested_dir = Path(raw_dir).expanduser() if raw_dir else Path.home() / ".local" / "share" / "pocketcloud"
    data_dir = _private_home_path(requested_dir)

    port = _positive_int("POCKETCLOUD_PORT", 8765)
    if not 1024 <= port <= 65535:
        raise ValueError("POCKETCLOUD_PORT must be between 1024 and 65535")

    max_database_bytes = _positive_int("POCKETCLOUD_MAX_DATABASE_BYTES", DEFAULT_MAX_DATABASE_BYTES)
    min_free_bytes = _positive_int("POCKETCLOUD_MIN_FREE_BYTES", DEFAULT_MIN_FREE_BYTES, allow_zero=True)
    return Settings(
        data_dir=data_dir,
        port=port,
        max_database_bytes=max_database_bytes,
        min_free_bytes=min_free_bytes,
    )


def require_unprivileged() -> None:
    get_effective_uid = getattr(os, "geteuid", None)
    if get_effective_uid is None:
        raise RuntimeError("PocketCloud Stage 1 requires a POSIX/Termux user account")
    if get_effective_uid() == 0:
        raise RuntimeError("PocketCloud must not run as root")


def _effective_uid() -> int:
    get_effective_uid = getattr(os, "geteuid", None)
    if get_effective_uid is None:
        raise RuntimeError("PocketCloud Stage 1 requires POSIX file ownership checks")
    return get_effective_uid()


def prepare_data_dir(path: Path) -> None:
    require_unprivileged()
    path = _private_home_path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise PermissionError("PocketCloud data path is not a directory")

    try:
        path.chmod(0o700)
    except OSError as exc:
        raise PermissionError("could not secure PocketCloud data directory permissions") from exc

    metadata = path.stat()
    if metadata.st_uid != _effective_uid() or metadata.st_mode & 0o077:
        raise PermissionError("PocketCloud data directory must be owned by this user and private (mode 0700)")


def secure_private_file(path: Path, mode: int = 0o600) -> None:
    """Create/secure a regular user-owned file; fail closed on symlinks or weak permissions."""
    require_unprivileged()
    if path.is_symlink():
        raise PermissionError("PocketCloud refuses a symlink for private runtime state")
    parent = _private_home_path(path.expanduser().parent)
    path = parent / path.name
    if path.is_symlink():
        raise PermissionError("PocketCloud refuses a symlink for private runtime state")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, mode)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != _effective_uid():
            raise PermissionError("PocketCloud state file must be a regular file owned by this user")
        try:
            os.fchmod(descriptor, mode)
        except OSError as exc:
            raise PermissionError("could not secure PocketCloud state file permissions") from exc
        metadata = os.fstat(descriptor)
        if metadata.st_mode & 0o077:
            raise PermissionError("PocketCloud state file permissions are not private (mode 0600)")
    finally:
        os.close(descriptor)
