# Decision Log

## D-001 — Stage-gated implementation

**Status:** Accepted from the supplied engineering brief. Stage 1 scope was approved by the user on 2026-11-02 with “continue”; Stage 2 scope was explicitly requested on 2026-11-02. Work proceeds only within reviewed stage boundaries. Neither Stage 1 nor Stage 2 hardware gates can pass without the actual phone/laptop.

## D-002 — Phone is the authority, not a single executor

**Status:** Accepted. The phone owns identity, desired state and assignment. A worker may finish an already-authorized lease and buffer a result during phone downtime, but does not assign new phone-owned jobs.

## D-003 — Rootless, local-first runtime

**Status:** Accepted and enforced in the Stage 1 host implementation. No root/exploit/system changes, mandatory hosted control plane, paid relay/API, or public admin endpoint. Each device owns its own local data store.

## D-004 — Approved handlers only

**Status:** Accepted and implemented for Stage 1. Registered handler IDs and strict payloads only; no arbitrary shell API or claim of strong isolation. The only current handler is deterministic `self_test.v1`. PRoot is not a VM/security boundary.

## D-005 — Delivery model

**Status:** Accepted. At-least-once delivery, persisted receipts/results, idempotency/deduplication, leases/fencing and explicit reconciliation. No universal exactly-once claim. Stage 1 quarantines unfinished jobs instead of replaying them.

## D-006 — Portable Stage 1 dependency set

**Status:** Revised and implemented. Direct pins are Starlette 1.10.0, Uvicorn 0.54.0 and SQLAlchemy 2.1.6. FastAPI/Pydantic Core and Alembic/Mako were removed from the runtime dependency path. A clean Linux environment resolves eight exact packages; an Android arm64 CPython 3.12 binary-only wheel resolution passed for the separate Termux lock. This is not a Termux-device test; device Python tags and install behavior remain open.

## D-007 — Repository license

**Status:** Accepted and implemented. The user chose MIT on 2026-11-02. See the repository `LICENSE` file; third-party components retain their own licenses.

## D-008 — Exclusive runtime ownership and protected storage

**Status:** Accepted and implemented on the Linux host. Refuse UID 0; require user-home paths; verify owner/private modes; use one advisory runtime lock before migration/recovery so concurrent startup cannot quarantine live work. Operators must keep state on local app-private storage; the runtime does not reliably fingerprint every filesystem/mount type.

## D-009 — Storage admission, never auto-prune

**Status:** Accepted and implemented for Stage 1 submissions. Default to a configurable 64 MiB SQLite footprint cap and 8 MiB free-space reserve; reject new work before persistence when capacity is insufficient. Never silently delete active or unresolved state. Backup, restore and retention management remain future work.

## D-010 — Checksummed project-owned SQLite migrations

**Status:** Accepted and implemented. Stage 1 applies immutable numbered SQL migrations with SHA-256 checksums and refuses modified applied migrations or schema gaps. This avoids shipping Alembic/Mako into the Termux runtime; the migration runner is intentionally small and must remain covered by tampering tests.

## D-011 — User-started, visible Android supervisor

**Status:** Accepted for the Stage 2 foundation. Start only from a visible user action; declare an appropriate foreground-service type; provide a persistent notification and explicit Stop; consume Termux 0.109+ one-shot result callbacks and remove the Stop notification only after exit code zero. Do not add boot auto-start, hidden persistence, arbitrary shell input, or an uptime guarantee. Android `specialUse`/distribution policy and target-device lifecycle behavior remain open gates.

## D-012 — Pairing is bootstrap, not remote execution

**Status:** Accepted for protocol v1. Use a five-minute one-use QR token, TLS SPKI pin, Android Keystore P-256 phone proof-of-possession, and explicit phone/laptop approval. The pairing endpoint only records a public phone key; no remote shell or job-dispatch endpoint is included. See `docs/PAIRING_PROTOCOL.md`.
