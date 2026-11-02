# Build Status — Stage 1

**Current phase:** Stage 1 host implementation and regression suite pass; awaiting actual Android/Termux verification before its release gate can pass.

## Implemented

The repository contains a loopback-only FastAPI runtime, separate liveness/readiness checks, SQLite/Alembic persistence, WAL/foreign keys/busy timeout/synchronous FULL, durable job/event records, strict schema and an 8 KiB request-body cap, one deterministic approved handler (`self_test.v1`), idempotency protection, result persistence before HTTP success, structured bounded logs, and quarantine of interrupted jobs as `needs_reconciliation`.

The runtime refuses root, restricts state to the current user's home directory, fails closed if private ownership/modes cannot be secured, and holds an exclusive per-data-directory lock before migrations/recovery. Job admission plus this bounded handler's state transitions are serialized. Configurable admission defaults are a 64 MiB SQLite page-count/database ceiling and 8 MiB minimum free-space threshold; submissions are rejected before persistence when checks fail. No active or unresolved state is automatically pruned. The free-space check is point-in-time; external applications can consume disk afterward. The runtime does not reliably fingerprint filesystem/mount types, so use local app-private Termux storage only.

Direct dependencies are pinned to FastAPI 0.162.0, Uvicorn 0.54.0, SQLAlchemy 2.1.6 and Alembic 1.20.1. The resolved lock is Linux x86_64 / CPython 3.12.3 specific; Android wheel/native-build compatibility remains open.

## Host evidence

Ten integration tests passed, including restart persistence, idempotency, recovery quarantine, root/out-of-home refusal, duplicate-process protection, concurrent near-capacity admission, both database/free-space rejection paths, request limits, and SQLite durability/page settings. The service is exercised via its launcher under Linux UID 1000. `compileall`, `pip check`, and Bash syntax checks also passed on the final code. See `docs/TEST_REPORT.md` for commands and environment.

## Not verified / not implemented

No target Android phone or Windows laptop is attached. Android Termux installation/execution, native service/notification, `RUN_COMMAND`, Doze/background/lifecycle/resource behavior and device recovery have not been tested. Windows capability discovery, GPU/CUDA, worker execution, secure pairing, LAN dispatch, offline laptop results, dashboard, backups/restore, corruption injection, independent security assessment and soak testing are not implemented or tested. The Stage 1 gate remains **not proven on target hardware**.