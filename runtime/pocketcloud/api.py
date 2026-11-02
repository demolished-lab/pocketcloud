from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from functools import partial
from typing import Any

from sqlalchemy import Engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from pocketcloud.config import Settings, load_settings, prepare_data_dir
from pocketcloud.db import create_sqlite_engine, make_session_factory
from pocketcloud.jobs import IdempotencyConflict, create_and_execute_job, serialize_job
from pocketcloud.models import Job
from pocketcloud.storage import StorageLimitReached

logger = logging.getLogger("pocketcloud.api")
MAX_REQUEST_BYTES = 8 * 1024
_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class DuplicateJSONKeyError(ValueError):
    pass


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateJSONKeyError("duplicate_json_key")
        value[key] = item
    return value


class MaxBodyBytesMiddleware:
    """Buffer only small local API bodies and reject larger requests with 413."""

    def __init__(self, app: Any, limit: int = MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        body = bytearray()
        while True:
            message = await receive()
            if message.get("type") == "http.disconnect":
                return
            if message.get("type") != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > self.limit:
                payload = json.dumps({"detail": "request_too_large"}, separators=(",", ":")).encode("utf-8")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())],
                    }
                )
                await send({"type": "http.response.body", "body": payload, "more_body": False})
                return
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)


def _error(status: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_submission(value: Any) -> tuple[str, str, dict[str, str]] | str:
    if not isinstance(value, dict) or set(value) != {"handler_id", "idempotency_key", "payload"}:
        return "invalid_request"
    if value["handler_id"] != "self_test.v1":
        return "invalid_handler"
    key = value["idempotency_key"]
    if not isinstance(key, str) or not _IDEMPOTENCY_RE.fullmatch(key):
        return "invalid_idempotency_key"
    payload = value["payload"]
    if not isinstance(payload, dict) or set(payload) != {"message"}:
        return "invalid_payload"
    message = payload["message"]
    if not isinstance(message, str):
        return "invalid_payload"
    message = message.strip()
    if not 1 <= len(message) <= 256:
        return "invalid_payload"
    return "self_test.v1", key, {"message": message}


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    factory: sessionmaker[Session] | None = None,
) -> Starlette:
    settings = settings or load_settings()
    prepare_data_dir(settings.data_dir)
    engine = engine or create_sqlite_engine(settings.database_url, settings.max_database_bytes)
    factory = factory or make_session_factory(engine)

    async def liveness(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "component": "pocketcloud-runtime", "observed_at": _now()})

    async def readiness(_request: Request) -> JSONResponse:
        try:
            with factory() as session:
                session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.warning("readiness_database_unavailable", extra={"diagnostic_code": type(exc).__name__})
            return _error(503, "database_unavailable")
        return JSONResponse({"status": "ok", "component": "pocketcloud-runtime", "observed_at": _now()})

    async def submit_job(request: Request) -> Response:
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return _error(415, "content_type_must_be_application_json")
        try:
            value = json.loads(await request.body(), object_pairs_hook=_unique_json_object)
        except (json.JSONDecodeError, UnicodeDecodeError, DuplicateJSONKeyError):
            return _error(422, "invalid_json")
        parsed = _parse_submission(value)
        if isinstance(parsed, str):
            return _error(422, parsed)
        handler_id, idempotency_key, payload = parsed

        try:
            job_id, is_new = await __import__("anyio").to_thread.run_sync(
                partial(
                    create_and_execute_job,
                    factory,
                    handler_id,
                    idempotency_key,
                    payload,
                    database_path=settings.database_path,
                    max_database_bytes=settings.max_database_bytes,
                    min_free_bytes=settings.min_free_bytes,
                )
            )
        except IdempotencyConflict as exc:
            return _error(409, str(exc))
        except StorageLimitReached as exc:
            logger.warning("job_rejected_by_storage_policy", extra={"diagnostic_code": str(exc)})
            return _error(507, str(exc))
        except SQLAlchemyError as exc:
            logger.error("job_persistence_failed", extra={"diagnostic_code": type(exc).__name__})
            return _error(503, "job_persistence_unavailable")

        def load_serialized_job() -> dict[str, Any] | None:
            with factory() as session:
                job = session.scalar(select(Job).where(Job.id == job_id))
                return serialize_job(job) if job is not None else None

        job_body = await __import__("anyio").to_thread.run_sync(load_serialized_job)
        if job_body is None:
            logger.error("persisted_job_not_found", extra={"job_id": job_id})
            return _error(500, "job_state_unavailable")
        return JSONResponse(job_body, status_code=201 if is_new else 200)

    async def get_job(request: Request) -> Response:
        job_id = request.path_params["job_id"]
        try:
            with factory() as session:
                job = session.scalar(select(Job).where(Job.id == job_id))
                if job is None:
                    return _error(404, "job_not_found")
                return JSONResponse(serialize_job(job))
        except SQLAlchemyError as exc:
            logger.error("job_lookup_failed", extra={"diagnostic_code": type(exc).__name__})
            return _error(503, "job_state_unavailable")

    app = Starlette(
        routes=[
            Route("/livez", liveness, methods=["GET"]),
            Route("/readyz", readiness, methods=["GET"]),
            Route("/v1/jobs", submit_job, methods=["POST"]),
            Route("/v1/jobs/{job_id:str}", get_job, methods=["GET"]),
        ]
    )
    app.add_middleware(MaxBodyBytesMiddleware)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = factory
    return app
