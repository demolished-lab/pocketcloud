from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from pocketcloud.config import Settings, load_settings, prepare_data_dir
from pocketcloud.db import create_sqlite_engine, make_session_factory
from pocketcloud.jobs import IdempotencyConflict, create_and_execute_job, serialize_job
from pocketcloud.models import Job
from pocketcloud.storage import StorageLimitReached

logger = logging.getLogger("pocketcloud.api")
MAX_REQUEST_BYTES = 8 * 1024


class MaxBodyBytesMiddleware:
    """Buffer only small local API bodies and reject larger requests with 413."""

    def __init__(self, app: object, limit: int = MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: dict[str, object], receive: object, send: object) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)  # type: ignore[operator]
            return

        receive_fn = receive
        send_fn = send
        body = bytearray()
        while True:
            message = await receive_fn()  # type: ignore[operator]
            if message.get("type") == "http.disconnect":
                return
            if message.get("type") != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > self.limit:
                payload = json.dumps({"detail": "request_too_large"}, separators=(",", ":")).encode("utf-8")
                await send_fn(  # type: ignore[operator]
                    {
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())],
                    }
                )
                await send_fn(  # type: ignore[operator]
                    {"type": "http.response.body", "body": payload, "more_body": False}
                )
                return
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive() -> dict[str, object]:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive_fn()  # type: ignore[operator]

        await self.app(scope, replay_receive, send_fn)  # type: ignore[operator]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SelfTestPayload(StrictModel):
    message: str = Field(min_length=1, max_length=256)


class JobSubmission(StrictModel):
    handler_id: Literal["self_test.v1"]
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    payload: SelfTestPayload


class JobEventResponse(StrictModel):
    status: str
    diagnostic_code: str | None
    created_at: str


class JobResponse(StrictModel):
    id: str
    handler_id: str
    status: str
    attempt: int
    result: dict[str, str] | None
    error_code: str | None
    created_at: str
    updated_at: str
    events: list[JobEventResponse]


class HealthResponse(StrictModel):
    status: Literal["ok"]
    component: str
    observed_at: str


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    prepare_data_dir(settings.data_dir)
    engine = engine or create_sqlite_engine(settings.database_url, settings.max_database_bytes)
    factory = factory or make_session_factory(engine)

    app = FastAPI(title="PocketCloud Local Runtime", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(MaxBodyBytesMiddleware)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = factory

    @app.get("/livez", response_model=HealthResponse)
    def liveness() -> dict[str, str]:
        return {"status": "ok", "component": "pocketcloud-runtime", "observed_at": _now()}

    @app.get("/readyz", response_model=HealthResponse)
    def readiness() -> dict[str, str]:
        try:
            with factory() as session:
                session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.warning("readiness_database_unavailable", extra={"diagnostic_code": type(exc).__name__})
            raise HTTPException(status_code=503, detail="database_unavailable") from exc
        return {"status": "ok", "component": "pocketcloud-runtime", "observed_at": _now()}

    @app.post("/v1/jobs", response_model=JobResponse, status_code=201)
    def submit_job(submission: JobSubmission, response: Response) -> dict[str, object]:
        try:
            job_id, is_new = create_and_execute_job(
                factory,
                submission.handler_id,
                submission.idempotency_key,
                submission.payload.model_dump(mode="json"),
                database_path=settings.database_path,
                max_database_bytes=settings.max_database_bytes,
                min_free_bytes=settings.min_free_bytes,
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except StorageLimitReached as exc:
            logger.warning("job_rejected_by_storage_policy", extra={"diagnostic_code": str(exc)})
            raise HTTPException(status_code=507, detail=str(exc)) from exc
        if not is_new:
            response.status_code = 200

        with factory() as session:
            job = session.scalar(select(Job).where(Job.id == job_id))
            if job is None:
                logger.error("persisted_job_not_found", extra={"job_id": job_id})
                raise HTTPException(status_code=500, detail="job_state_unavailable")
            return serialize_job(job)

    @app.get("/v1/jobs/{job_id}", response_model=JobResponse)
    def get_job(job_id: str) -> dict[str, object]:
        with factory() as session:
            job = session.scalar(select(Job).where(Job.id == job_id))
            if job is None:
                raise HTTPException(status_code=404, detail="job_not_found")
            return serialize_job(job)

    return app
