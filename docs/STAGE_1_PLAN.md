# Stage 1 — Rootless Runtime Plan

**Status:** Approved by the user in chat on 2026-11-02. The host runtime now passes 20 integration tests. The Stage 1 release gate remains open because no target Android/Termux device is attached. This is still a local runtime foundation, not the complete platform.

## Outcome

Establish a minimal Python runtime that can run rootlessly in the intended Termux environment, owns local durable state, exposes accurate liveness/readiness, and can execute a deliberately harmless registered test handler with persisted job state. The gate is not passed until this behavior is demonstrated on the actual supported phone/Termux combination. Desktop-only testing is useful but not a substitute.

## Implemented scope

The Stage 1 code is laid out as `runtime/pocketcloud/{api.py,config.py,db.py,models.py,jobs.py,handlers.py,storage.py,logging_setup.py,migrations.py}` with immutable checksummed SQL schema versions in `runtime/pocketcloud/migrations/`, a manual launcher and fixed-verb supervisor script in `scripts/termux/`, and host integration tests in `tests/`. It includes a loopback-only API, liveness/readiness, SQLite WAL/foreign keys/busy timeout/synchronous FULL, durable jobs and audit events, strict request validation and an 8 KiB body cap, duplicate-key JSON rejection, one harmless registered handler, idempotency, bounded logs, startup quarantine for unfinished jobs, and corruption detection that refuses to silently rewrite a damaged DB.

Runtime startup refuses UID 0, requires the state path to be a dedicated child of the current user's home (rejecting the home directory itself before permission changes), verifies private ownership/modes, and acquires an exclusive per-data-directory lock before migrations/recovery. Job admission and this bounded handler's state transitions are serialized. Configurable admission defaults are a 64 MiB SQLite page/database ceiling and an 8 MiB minimum free-space threshold; database/WAL/SHM preflight rejects new work before persistence when checks fail. No automatic pruning/deletion occurs. The supervisor refuses to report a successful stop when a live PID fails ownership validation and preserves its PID record. Free-space checks are point-in-time, and underlying filesystem types are not reliably detected; use local app-private Termux storage.

Host validation covers parallel duplicate idempotency, malformed/extra fields, nested duplicate JSON keys, migration tampering/gaps, injected SQLite page corruption, corrupt-header preservation, fixed-verb supervisor start/status/stop, unrelated-live-PID stop refusal, home-path rejection without chmod, state-file symlink rejection, and a bounded 15-minute soak. The soak completed 180 readiness/idempotency cycles with zero failures; this is not a long-duration reliability or Android-device soak. The harness supports longer operator-run durations.

## Dependency record

Direct pins are Starlette 1.10.0, Uvicorn 0.54.0, and SQLAlchemy 2.1.6. FastAPI/Pydantic Core and Alembic/Mako were removed from the runtime path to eliminate the known Android compiled-wheel blocker and dependency build overhead. The new lock contains eight exact packages; a binary-only Android arm64 CPython 3.12 wheel resolution passed for `requirements-termux.lock`. This does not prove compatibility with the actual Termux Python installation or phone.

## Stage 1 gate

The gate requires reproducible setup on the target phone without root; the backend starts in the intended rootless runtime; health/readiness reflect service state; a registered safe job survives process restart; migrations and SQLite durability behavior are evidenced; and failures have useful diagnostic context. Host tests establish only Linux sandbox behavior. If device access remains unavailable, the gate must stay **not proven on target hardware**.

## Project structure

```text
runtime/pocketcloud/
  api.py config.py db.py models.py jobs.py handlers.py storage.py logging_setup.py migrations.py
  migrations/0001_initial_jobs.sql
scripts/termux/{run.sh,supervisor.sh,README.md}
scripts/testing/soak_runtime.py
tests/test_runtime.py
requirements.in requirements.lock requirements-termux.in requirements-termux.lock
pyproject.toml
```

Stage 2 adds the native Android supervisor and phone-to-laptop pairing bootstrap in separate areas; neither expands the Stage 1 hardware evidence. The Android service/permission matrix, Termux installation, Windows target, long soak, backup/restore, and independent security assessment remain gates.
