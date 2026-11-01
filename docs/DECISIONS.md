# Decision Log

## D-001 — Stage-gated implementation

**Status:** Accepted from the supplied engineering brief. We will not implement the entire product in one pass. Work stops after the Stage 0 package until the Stage 1 plan and required target-device details are reviewed.

## D-002 — Phone is the authority, not a single executor

**Status:** Accepted. The phone owns identity, desired state and assignment. A worker may finish an already-authorized lease and buffer a result during phone downtime, but does not assign new phone-owned jobs.

## D-003 — Rootless, local-first runtime

**Status:** Accepted. No root/exploit/system changes, mandatory hosted control plane, paid relay/API, or public admin endpoint. Each device owns its own local data store.

## D-004 — Approved handlers only

**Status:** Accepted. Registered handler IDs and strict payloads only; no arbitrary shell API or claim of strong isolation. PRoot is not a VM/security boundary.

## D-005 — Delivery model

**Status:** Accepted. At-least-once delivery, persisted receipts/results, idempotency/deduplication, leases/fencing and explicit reconciliation. No universal exactly-once claim.

## D-006 — Initial dependency proposal

**Status:** Proposed. Python + FastAPI/Uvicorn + SQLAlchemy/Alembic + SQLite for the first runtime, subject to exact version/license/maintenance/footprint/offline review before installation and lockfile creation.

## D-007 — Repository license

**Status:** Unresolved. The repo is requested as public; no license is selected. Do not add a license automatically because public visibility is not a reuse license.