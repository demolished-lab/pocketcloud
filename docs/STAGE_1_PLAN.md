# Stage 1 — Rootless Runtime Plan

**Status: Proposed; implementation is paused until approved.** This is the first implementation stage only, not a claim that the complete platform can be built or verified in this session.

## Outcome

Establish a minimal Python runtime that can run rootlessly in the intended Termux environment, owns local durable state, exposes accurate liveness/readiness, and can execute a deliberately harmless registered test handler with persisted job state. The Stage 1 gate is not passed until this behavior is demonstrated on the actual supported phone/Termux combination. A desktop-only test is useful but not a substitute.

## Design and interfaces

- `runtime/pocketcloud/config`: validated local configuration, with conservative configurable defaults and no hard-coded universal battery/CPU/RAM promises.
- `runtime/pocketcloud/storage`: SQLite database owned only by this device, transactions, foreign keys, busy timeout, and startup schema migrations.
- `runtime/pocketcloud/jobs`: small durable state machine for local registered handlers, including unique job ID, idempotency key, attempt count, timestamps, and explicit terminal/error states.
- `runtime/pocketcloud/compute`: allowlisted handler registry and bounded process lifecycle; no user-provided shell string and no arbitrary code endpoint.
- `runtime/pocketcloud/api`: local health, readiness, diagnostics, and a narrow job submission/status API. Bind to loopback by default; do not expose a public admin port.
- `scripts/termux`: documented rootless setup and controlled start/stop commands. Keep the Termux RUN_COMMAND integration decision open until its permissions and target-device behavior are verified.

Use a Python package layout, `pyproject.toml` with exact dependency pins and a generated lockfile, tests, and operator documentation. Stage 1 should avoid dashboard, pairing, remote networking, background-service claims, arbitrary workload containers, Windows execution, and optional AI/agent features.

## Proposed dependencies

FastAPI, Uvicorn, SQLAlchemy, Alembic, and Pydantic are the candidate application dependencies. Before adding them, record their exact versions, licenses, maintenance status, Python compatibility, dependency footprint, and whether installation can be performed offline from a saved wheel set. Prefer maintained compatible versions; pin them. Python's standard library should be used for logging, path handling, subprocess invocation, and SQLite administration where it does not conflict with the approved SQLAlchemy/Alembic storage design.

## Review decisions required before implementation

1. Approve this limited Stage 1 scope and its device-based exit gate.
2. Confirm the target Android model/version and that Termux may be installed from a compatible trusted distribution.
3. Choose whether the repo should carry an explicit open-source license; it is currently unlicensed despite being public.
4. Confirm whether the Windows laptop is available later; Windows worker work remains out of Stage 1.

## Stage 1 gate

The gate requires a reproducible setup on the target phone without root; the backend starts using the intended rootless runtime; health and readiness accurately reflect service state; a registered safe job survives a process restart; migrations and SQLite durability behavior are evidenced; and failures have useful diagnostic context. If direct device access remains unavailable, the code may be authored and host-tested only after approval, but the gate must remain marked **not proven on target hardware**.

## Project structure proposal

```text
runtime/pocketcloud/{api,compute,config,jobs,storage}/
scripts/termux/
tests/{unit,integration}/
docs/
pyproject.toml
```

Add Android Kotlin supervisor, Windows worker, and dashboard directories only when their stages begin and their interfaces have been reviewed. Do not create empty folders to mimic the full reference architecture.