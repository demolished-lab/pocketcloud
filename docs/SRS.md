# Software Requirements Specification

This document records baseline requirements from the supplied PocketCloud engineering brief. Requirements are staged; a later-stage requirement is not an implemented feature until evidence exists.

## Runtime and service lifecycle

The Android runtime shall require no root, bootloader unlock, custom ROM, system-partition modification, or exploit. The Android layer shall use legitimate platform lifecycle mechanisms and declare a foreground-service type matching its real work. It shall show a truthful persistent notification while an eligible service is active and provide a clear stop/control path. It shall disclose background restriction, battery optimization, thermal and memory signal availability where permissions/platform APIs allow. WorkManager may be used for suitable deferrable work but shall not be presented as exact cron. Force-stop shall require manual relaunch; reboot recovery is best-effort.

## Jobs and execution

Every job shall have a globally unique ID, approved task/handler and version, idempotency key, payload schema version, timestamps/deadline, priority, resource requirements, retry/cancel policy, assigned worker, lease ID/expiry, epoch/fencing value, attempt count, status, result reference/checksum, and acknowledgement state. The main path is `pending → dispatched → leased → running → result_persisted → acknowledged → completed`. Supported alternate states include `retry_wait`, `failed`, `paused`, `cancelled`, `expired`, and `needs_reconciliation`.

Workers shall persist a receipt/lease before execution and persist the result locally before reporting completion. Network failure shall retain results for bounded-backoff reporting. Uncertain outcomes shall enter reconciliation rather than blindly replaying a potentially non-idempotent effect. Only registered approved handlers may execute; no arbitrary shell endpoint exists.

## Identity, pairing, and authorization

Pairing shall use a short-lived single-use challenge, explicit mutual user approval, locally generated device keys, identity/fingerprint display, mutual challenge-response, authenticated encryption, and a persisted trust record. QR content shall not contain a permanent private secret. The system shall support revocation, key rotation, session invalidation, and bounded redacted audit history. Discovery announcements alone shall never establish trust. Roles/capabilities shall distinguish administration, worker, and read-only actions.

## Storage and observability

Each device shall own a separate SQLite database; a database file shall not be concurrently edited over a network. Storage shall use transactions, foreign keys, busy timeouts, migrations, checksummed artifact metadata, safe atomic writes where supported, quotas, retention/log rotation, reserved recovery space, backup, and demonstrated restore. Storage exhaustion shall reject new artifact writes safely without silently deleting authoritative task state.

Structured diagnostic events shall include timestamp, severity, component, device/correlation/job IDs where applicable, and sanitized context. Health checks shall distinguish liveness from readiness. Telemetry shall expose source/provenance such as OS value, unavailable, denied, or estimated. Warnings shall describe impact and next action. Diagnostics exports shall redact secrets and personal data.

## Resource protection

Modes shall include Active, Adaptive, Charging, Critical, and Recovery. Optional work shall yield under critical thermal, memory, battery, or user-activity conditions when signals are available. Admission/concurrency reduction is preferred over unsupported claims of OS-enforced caps. Pause reasons and resume conditions shall be visible, with hysteresis/minimum dwell time to avoid oscillation. Unnecessary personal-data collection and private app-activity inference are prohibited.

## Networking and dashboard

Connection preference is same-LAN direct, configured private VPN, optional relay adapter, then offline queue. Network changes shall not erase job state or persisted results. No public admin port shall be enabled by default. The eventual dashboard shall reflect actual health, device identity/status, jobs, workloads, storage, telemetry, trust/audit, warnings and diagnostics. Every visible control must call a real backend operation; fabricated telemetry and simulated success are prohibited.

## Proposed measurable objectives

The engineering brief proposes same-LAN pairing under 30 seconds, worker capability registration within 5 seconds after authenticated connection, local dispatch under 2 seconds in normal LAN conditions, recovery under 30 seconds after service restart is permitted, durable commit without loss, duplicate-effect prevention for registered idempotent handlers, offline result survival across process restart, backup restore, and practical 1/6/12/24-hour soak tests. These are objectives, not guarantees, and require actual-device measurement.