# Architecture

## System model

PocketCloud is a distributed personal service, not a collection of containers masquerading as a cloud. The phone is the control authority; it is not the only executor. The laptop can finish valid work for which it already holds a persisted lease and can buffer the result while the phone is unavailable. It cannot originate/reassign phone-owned tasks. Phone and laptop keep separate authoritative local databases.

## Planes and modules

- **Experience:** eventual Android setup, overview, jobs, devices, compute, storage, security, monitoring and diagnostics views.
- **Identity/control:** device IDs, pairing, authorization, registry, revocation, desired state and audit.
- **Coordination/resilience:** dispatcher, leases, retry controller, heartbeat, offline event/result buffer, reconciler, recovery and conflict quarantine.
- **Compute:** allowlisted handlers, process manager, timeout/output limits, resource-aware admission and cancellation.
- **Storage:** per-device SQLite, migrations, artifacts, checksums, quotas, log rotation and backup/restore.
- **Network:** LAN discovery (hint only), authenticated encrypted transport, reconnect negotiation, optional VPN/relay adapters and offline queue.
- **Platform adapters:** narrow Termux bridge/native Android supervisor; separate Windows worker lifecycle and capability probes.

## Authority and task flow

The phone creates/persists a job before exposing it. Dispatcher sends a registered task description to a trusted worker, which persists receipt and lease before execution. Handler output is written to worker-local storage with checksum before completion is reported. Phone validates lease epoch and idempotency state, persists the returned result and acknowledgement transactionally, then marks completion. Retries are at-least-once and effects are made idempotent where possible. An uncertain outcome becomes `needs_reconciliation`; no silent discard or unsafe blind replay.

## Failure behavior

Control-plane/dashboard failure must not corrupt or terminate authorized work already held by the worker. Worker loss or sleep is represented as offline/sleeping/unreachable/maintenance, not a fabricated online status. Network changes do not erase durable job/result state. Storage exhaustion rejects new artifact writes while preserving task state. Revocation invalidates future sessions/leases, and in-flight work is handled under explicit policy. Every failure records timestamp, component, impact, context, and recovery action.

## Deployment order

Prove local rootless persistence first. Then validate native Android lifecycle/resource signals on the real phone, build persistent job/compute foundation, implement pairing, build worker capability discovery, and only then distributed execution/reconciliation. LAN networking and dashboard follow the core protocol. Security hardening, installers and the full end-to-end demo come after working interfaces. No cloud control plane is required for local operation.