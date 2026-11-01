# Technical Requirements Document

## Runtime topology

The phone and laptop run independent local Python services and independent SQLite databases. The phone is the single logical authority for desired state and assignment. The Windows worker accepts only authenticated phone-authorized leases and can buffer already-authorized work/results during disconnects. The web/dashboard layer is a client of the control API, not the execution data plane.

## Candidate technology

The backend and Windows worker use Python. The Android runtime candidate is Termux with FastAPI/Uvicorn, SQLAlchemy and Alembic. Kotlin is limited to native lifecycle, notification, platform signals and a narrow Termux integration only if device evidence supports it. Windows capability detection will use OS APIs and carefully selected maintained Python packages only after its stage. The dashboard framework remains undecided until service/API contracts exist.

The candidate Python packages are not yet installed or locked. Before implementation, record exact versions, licensing, maintenance/release status, Python compatibility, transitive dependency footprint and offline installation path in a lockfile/SBOM or dependency inventory. FastAPI and Uvicorn support the local API; SQLAlchemy and Alembic satisfy the brief's persistence/migration requirements. Avoid dependencies that force hosted services, telemetry, accounts, API keys, or online execution. Use a pinned install set and document updates/rollback.

## Data and protocol invariants

Use explicit API schemas with payload-size limits and strict validation. Each device writes only its own DB. Persist state transitions transactionally before acknowledgement. Use at-least-once transport plus idempotency/deduplication rather than a universal exactly-once claim. Leases include epochs/fencing values. Ambiguous execution state is quarantined for reconciliation. Artifacts use metadata, checksums, size limits, and safe write/rename behavior. Logs are structured and secret-redacted.

## Security boundaries

Pairing uses established cryptographic libraries/protocols; no custom cryptography. Private keys are generated on-device and stored using platform-appropriate protection where feasible. Authenticated encrypted sessions use device-bound credentials and pinned identity. Discovery is unauthenticated hinting only. There is no remote shell API. Per-workload directories improve organization but do not constitute a secure sandbox; PRoot is not a VM or isolation boundary.

## Repository areas

The initial implementation should add only `runtime/pocketcloud` modules for config, API, storage, jobs and approved compute handlers; `scripts/termux` for setup/service operations; tests; and docs. `android-supervisor` begins only after the Termux bridge and device API facts are known. `windows-worker` begins in its own stage with capability probes and durable lease/result storage. A real dashboard is deferred until the API contract and backing operations are implemented.

## Operational constraints

LAN-first control is private and authenticated. Local-only endpoints bind to loopback; any LAN listener requires pairing, auth and an explicit user action. Network interface/provider behavior is behind an abstraction. Exponential backoff includes jitter and bounded retries. The runtime must work offline after installation and must preserve queued durable state through network changes.