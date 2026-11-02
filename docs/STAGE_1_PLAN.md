# Stage 1 — Rootless Runtime Plan

**Status:** Approved by the user in chat on 2026-11-02 with “continue”; the host implementation passes ten integration tests. The Stage 1 release gate remains open because no target Android/Termux device is attached. This is the first implementation stage only, not the complete platform.

## Outcome

Establish a minimal Python runtime that can run rootlessly in the intended Termux environment, owns local durable state, exposes accurate liveness/readiness, and can execute a deliberately harmless registered test handler with persisted job state. The gate is not passed until this behavior is demonstrated on the actual supported phone/Termux combination. Desktop-only testing is useful but not a substitute.

## Implemented scope

The Stage 1 code is laid out as `runtime/pocketcloud/{api.py,config.py,db.py,models.py,jobs.py,handlers.py,storage.py,logging_setup.py}` with Alembic migrations in `runtime/pocketcloud/migrations/`, a manual Termux launcher in `scripts/termux/`, and host integration tests in `tests/`. It includes a loopback-only API, live/readiness endpoints, SQLite migrations and transactions, foreign keys, busy timeout, WAL and synchronous FULL, a durable job/event state machine, strict payload validation and an 8 KiB body cap, one deterministic approved handler, idempotency protection, bounded structured logs, and startup quarantine for unfinished jobs.

Runtime startup refuses UID 0, restricts state to the current user's home, verifies private ownership/modes, and acquires an exclusive per-data-directory lock before migrations/recovery. Job admission and this bounded handler's state transitions are serialized. Configurable admission defaults are a 64 MiB SQLite page/database ceiling and an 8 MiB minimum free-space threshold; database/WAL/SHM preflight rejects new work before persistence when checks fail. No automatic pruning/deletion occurs. Free-space checks are point-in-time, and underlying filesystem types are not reliably detected; use local app-private Termux storage.

It excludes the native Android supervisor, foreground service, Termux `RUN_COMMAND` integration, resource manager, pairing, remote/LAN networking, Windows execution, dashboard, and agents. Those are later stages with separate gates.

## Dependency record

Direct pins are FastAPI 0.162.0, Uvicorn 0.54.0, SQLAlchemy 2.1.6 and Alembic 1.20.1. Package metadata and rationale are in `docs/TRD.md`; the resolved Linux CPython 3.12 lock is `requirements.lock`. Python 3.11 or later is the declared floor. Termux wheel/native-build compatibility is unverified.

## Stage 1 gate

The gate requires reproducible setup on the target phone without root; the backend starts in the intended rootless runtime; health/readiness reflect service state; a registered safe job survives process restart; migrations and SQLite durability behavior are evidenced; and failures have useful diagnostic context. Host tests establish only Linux sandbox behavior. If device access remains unavailable, the gate must stay **not proven on target hardware**.

## Project structure

```text
runtime/pocketcloud/
  api.py config.py db.py models.py jobs.py handlers.py storage.py logging_setup.py
  migrations/{env.py,versions/}
scripts/termux/{run.sh,README.md}
tests/test_runtime.py
docs/{STAGE_1_PLAN,BUILD_STATUS,TEST_REPORT,TRD}.md
requirements.in
requirements.lock
pyproject.toml
```

Add Android Kotlin supervisor, Windows worker, and dashboard code only when those stages begin and their interfaces have been reviewed. Do not create empty folders to mimic the full proposed architecture.