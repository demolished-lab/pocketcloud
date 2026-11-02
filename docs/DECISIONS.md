# Decision Log

## D-001 — Stage-gated implementation

**Status:** Accepted from the supplied engineering brief. Stage 1 scope was approved by the user on 2026-11-02 with “continue.” Work proceeds only to the next approved stage; the Android verification gate remains open.

## D-002 — Phone is the authority, not a single executor

**Status:** Accepted. The phone owns identity, desired state and assignment. A worker may finish an already-authorized lease and buffer a result during phone downtime, but does not assign new phone-owned jobs.

## D-003 — Rootless, local-first runtime

**Status:** Accepted and enforced in Stage 1 CLI. No root/exploit/system changes, mandatory hosted control plane, paid relay/API, or public admin endpoint. Each device owns its own local data store.

## D-004 — Approved handlers only

**Status:** Accepted and implemented for Stage 1. Registered handler IDs and strict payloads only; no arbitrary shell API or claim of strong isolation. The only current handler is deterministic `self_test.v1`. PRoot is not a VM/security boundary.

## D-005 — Delivery model

**Status:** Accepted. At-least-once delivery, persisted receipts/results, idempotency/deduplication, leases/fencing and explicit reconciliation. No universal exactly-once claim. Stage 1 quarantines unfinished jobs instead of replaying them.

## D-006 — Initial dependency set

**Status:** Accepted for Stage 1. Exact pins: FastAPI 0.162.0, Uvicorn 0.54.0, SQLAlchemy 2.1.6, Alembic 1.20.1, with a resolved Linux CPython 3.12 lock. License/version rationale is in `docs/TRD.md`. Android install/build compatibility and dependency hashes remain unverified/open.

## D-007 — Repository license

**Status:** Unresolved. The repo is requested as public; no license is selected. Public visibility is not a reuse license.

## D-008 — Exclusive runtime ownership and protected storage

**Status:** Accepted and implemented. Refuse UID 0; require user-home paths; verify owner/private POSIX modes; use one advisory runtime lock before migration/recovery so concurrent startup cannot quarantine live work. Operators must keep the state on local app-private storage; the runtime does not reliably fingerprint every filesystem/mount type.

## D-009 — Storage admission, never auto-prune

**Status:** Accepted and implemented for new Stage 1 job submissions. Default to a configurable 64 MiB SQLite footprint cap and 8 MiB free-space reserve; reject new work before persistence when capacity is insufficient. Never silently delete active or unresolved state. Backup, restore and retention management remain future work.