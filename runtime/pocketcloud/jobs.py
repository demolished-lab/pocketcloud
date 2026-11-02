from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from pocketcloud.handlers import get_handler
from pocketcloud.models import Job, JobEvent
from pocketcloud.storage import StorageLimitReached, ensure_write_capacity

logger = logging.getLogger("pocketcloud.jobs")
_CREATE_JOB_LOCK = threading.RLock()


class IdempotencyConflict(Exception):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def payload_digest(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def create_job(
    factory: sessionmaker[Session],
    handler_id: str,
    idempotency_key: str,
    payload: dict[str, Any],
    *,
    database_path: Path,
    max_database_bytes: int,
    min_free_bytes: int,
) -> tuple[str, bool]:
    payload_json = canonical_json(payload)
    digest = payload_digest(payload_json)

    # This process-local lock serializes admission checks; runtime_lock prevents
    # a second service process from sharing the same SQLite state.
    with _CREATE_JOB_LOCK:
        with factory() as session:
            existing = session.scalar(
                select(Job).where(Job.handler_id == handler_id, Job.idempotency_key == idempotency_key)
            )
            if existing:
                if existing.payload_sha256 != digest:
                    raise IdempotencyConflict("idempotency_key_reused_with_different_payload")
                return existing.id, False

        ensure_write_capacity(
            database_path,
            estimated_write_bytes=len(payload_json.encode("utf-8")) + 16384,
            max_database_bytes=max_database_bytes,
            min_free_bytes=min_free_bytes,
        )
        now = utcnow()
        job_id = str(uuid4())
        try:
            with factory.begin() as session:
                job = Job(
                    id=job_id,
                    handler_id=handler_id,
                    idempotency_key=idempotency_key,
                    payload_sha256=digest,
                    payload_json=payload_json,
                    status="pending",
                    attempt=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add(job)
                session.add(JobEvent(job_id=job_id, status="pending", diagnostic_code="job_persisted", created_at=now))
        except IntegrityError:
            # The database unique constraint remains authoritative if another
            # caller bypasses this process-local serialization.
            with factory() as session:
                existing = session.scalar(
                    select(Job).where(Job.handler_id == handler_id, Job.idempotency_key == idempotency_key)
                )
                if existing and existing.payload_sha256 == digest:
                    return existing.id, False
                if existing:
                    raise IdempotencyConflict("idempotency_key_reused_with_different_payload")
            raise
        return job_id, True


def create_and_execute_job(
    factory: sessionmaker[Session],
    handler_id: str,
    idempotency_key: str,
    payload: dict[str, Any],
    *,
    database_path: Path,
    max_database_bytes: int,
    min_free_bytes: int,
) -> tuple[str, bool]:
    """Hold the admission lock through this bounded Stage 1 handler's final write."""
    with _CREATE_JOB_LOCK:
        job_id, is_new = create_job(
            factory,
            handler_id,
            idempotency_key,
            payload,
            database_path=database_path,
            max_database_bytes=max_database_bytes,
            min_free_bytes=min_free_bytes,
        )
        if is_new:
            _execute_job_serialized(factory, job_id)
        return job_id, True


def create_and_execute_job(
    factory: sessionmaker[Session],
    handler_id: str,
    idempotency_key: str,
    payload: dict[str, Any],
    *,
    database_path: Path,
    max_database_bytes: int,
    min_free_bytes: int,
) -> tuple[str, bool]:
    """Keep admission, commit, and this bounded handler lifecycle serialized."""
    with _CREATE_JOB_LOCK:
        job_id, is_new = create_job(
            factory,
            handler_id,
            idempotency_key,
            payload,
            database_path=database_path,
            max_database_bytes=max_database_bytes,
            min_free_bytes=min_free_bytes,
        )
        if is_new:
            _execute_job_serialized(factory, job_id)
        return job_id, is_new


def execute_job(factory: sessionmaker[Session], job_id: str) -> None:
    # The Stage 1 handler is bounded; serializing its transitions keeps
    # database growth aligned with the admission estimate.
    with _CREATE_JOB_LOCK:
        _execute_job_serialized(factory, job_id)


def _execute_job_serialized(factory: sessionmaker[Session], job_id: str) -> None:
    with factory.begin() as session:
        job = session.get(Job, job_id)
        if job is None or job.status != "pending":
            return
        now = utcnow()
        job.status = "running"
        job.updated_at = now
        session.add(JobEvent(job_id=job_id, status="running", diagnostic_code="handler_started", created_at=now))
        handler_id = job.handler_id
        payload = json.loads(job.payload_json)

    try:
        result = get_handler(handler_id)(payload)
        result_json = canonical_json(result)
    except Exception:
        logger.error("approved_handler_failed", extra={"job_id": job_id, "handler_id": handler_id})
        with factory.begin() as session:
            job = session.get(Job, job_id)
            if job is not None and job.status == "running":
                now = utcnow()
                job.status = "failed"
                job.error_code = "handler_failed"
                job.updated_at = now
                session.add(
                    JobEvent(job_id=job_id, status="failed", diagnostic_code="handler_failed", created_at=now)
                )
        return

    with factory.begin() as session:
        job = session.get(Job, job_id)
        if job is None or job.status != "running":
            return
        now = utcnow()
        job.result_json = result_json
        job.status = "completed"
        job.updated_at = now
        session.add(JobEvent(job_id=job_id, status="completed", diagnostic_code="result_persisted", created_at=now))


def reconcile_interrupted_jobs(factory: sessionmaker[Session]) -> int:
    """Quarantine unfinished attempts after process restart; never replay them blindly."""
    with factory.begin() as session:
        interrupted = list(session.scalars(select(Job).where(Job.status.in_(("pending", "running")))))
        now = utcnow()
        for job in interrupted:
            job.status = "needs_reconciliation"
            job.error_code = "process_interrupted"
            job.updated_at = now
            session.add(
                JobEvent(
                    job_id=job.id,
                    status="needs_reconciliation",
                    diagnostic_code="process_interrupted",
                    created_at=now,
                )
            )
        return len(interrupted)


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def serialize_job(job: Job) -> dict[str, Any]:
    events = sorted(job.events, key=lambda event: (event.created_at, event.id))
    return {
        "id": job.id,
        "handler_id": job.handler_id,
        "status": job.status,
        "attempt": job.attempt,
        "result": json.loads(job.result_json) if job.result_json is not None else None,
        "error_code": job.error_code,
        "created_at": utc_iso(job.created_at),
        "updated_at": utc_iso(job.updated_at),
        "events": [
            {
                "status": event.status,
                "diagnostic_code": event.diagnostic_code,
                "created_at": utc_iso(event.created_at),
            }
            for event in events
        ],
    }
