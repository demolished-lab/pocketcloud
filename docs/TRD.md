# Technical Requirements Document

## Runtime topology

The phone and laptop run independent local Python services and independent SQLite databases. The phone is the single logical authority for desired state and assignment. The Windows worker accepts only authenticated phone-authorized leases and can buffer already-authorized work/results during disconnects. The web/dashboard layer is a client of the control API, not the execution data plane.

## Stage 1 dependency decision

The Stage 1 direct pins are FastAPI 0.162.0, Uvicorn 0.54.0, SQLAlchemy 2.1.6, and Alembic 1.20.1. PyPI metadata lists FastAPI, SQLAlchemy and Alembic as MIT-licensed; Uvicorn is BSD-licensed. Their documented minimum Python versions range from 3.10 to 3.11, so the shared runtime floor is Python 3.11. The inspected host is Python 3.12.3. FastAPI uses Pydantic and Starlette; Alembic and SQLAlchemy form the local SQLite migration/storage layer; Uvicorn serves the loopback API [1] [2] [3] [4].

The complete resolved lock reflects Linux x86_64 / CPython 3.12.3, including transitive pins. It contains 18 distributions. On that host SQLAlchemy's wheel was 4.7 MB and Pydantic Core's wheel 2.2 MB; compressed download sizes are not the installed footprint. Runtime makes no network calls after installation. For an offline first install, prepare a platform-compatible local wheelhouse; this repository does not yet contain one.

Important compatibility caveat: the host-installed Pydantic Core wheel is a Linux x86_64 CPython wheel. This does not prove a compatible Android/Termux build exists. Android is not attached. Termux may need a platform wheel or native build toolchain, so dependency installation and execution remain an explicit target-device test and gate. The Windows worker will use a separately verified environment later; this lock is not a Windows artifact guarantee.

## Protocol, data and dependencies

Use explicit API schemas with payload-size limits and strict validation. Each device writes only its own database. Persist state transitions transactionally before acknowledgement. Use at-least-once transport plus idempotency/deduplication rather than a universal exactly-once claim. Leases include epochs/fencing values. Ambiguous execution state is quarantined for reconciliation. Artifacts use metadata, checksums, size limits, and safe write/rename behavior. Logs are structured and secret-redacted.

The Stage 1 service binds only to loopback, refuses UID 0, and requires its data path to resolve under the current user's home directory. It verifies owner/private POSIX modes for the state directory, DB and runtime lock; permission failures stop startup. An advisory OS lock permits one runtime process per data directory before migrations or restart recovery. Operators must select local app-private storage; the program cannot reliably identify every filesystem or network mount type.

New work has configurable admission thresholds: `POCKETCLOUD_MAX_DATABASE_BYTES` defaults to 64 MiB and `POCKETCLOUD_MIN_FREE_BYTES` defaults to 8 MiB. SQLite `max_page_count` is applied on Alembic and application connections. Preflight checks count the database plus WAL/SHM sidecars and include a conservative 16 KiB per-job write estimate; admission and this bounded handler's state transitions are serialized. New work is rejected before persistence when the database budget or free-space threshold fails. The free-space measurement is point-in-time and cannot prevent unrelated applications from consuming disk afterward. No active/unresolved jobs are automatically pruned. Backups, restore and retention policies are not implemented yet.

Before adding any further package, record exact version, license, maintenance state, Python/OS support, footprint, and offline behavior. Avoid dependencies that force hosted services, telemetry, accounts, API keys, or online execution. Pin transitive dependencies in the lockfile; add artifact hashes, update/rollback procedures, and revalidate advisories before release.

## Security boundaries

Pairing uses established cryptographic libraries/protocols; no custom cryptography. Private keys are generated on-device and stored using platform-appropriate protection where feasible. Authenticated encrypted sessions use device-bound credentials and pinned identity. Discovery is unauthenticated hinting only. There is no remote shell API. Per-workload directories improve organization but do not constitute a secure sandbox; PRoot is not a VM or isolation boundary.

## Repository areas

The Stage 1 implementation adds only `runtime/pocketcloud` modules for config, API, storage, jobs and approved compute handlers; `scripts/termux` for manual operations; tests; and docs. `android-supervisor` begins only after the Termux bridge and device API facts are known. `windows-worker` begins in its own stage with capability probes and durable lease/result storage. A real dashboard is deferred until the API contract and backing operations are implemented.

## Operational constraints

LAN-first control is private and authenticated. Stage 1 binds only to loopback; no LAN access or public admin port is enabled. Network interface/provider behavior is behind an abstraction in later stages. Exponential backoff includes jitter and bounded retries when networking is implemented. The runtime works offline after dependencies are installed and must preserve queued durable state through network changes.

## References

[1]: https://pypi.org/project/fastapi/0.162.0/ "FastAPI 0.162.0 on PyPI"
[2]: https://pypi.org/project/uvicorn/0.54.0/ "Uvicorn 0.54.0 on PyPI"
[3]: https://pypi.org/project/SQLAlchemy/2.1.6/ "SQLAlchemy 2.1.6 on PyPI"
[4]: https://pypi.org/project/alembic/1.20.1/ "Alembic 1.20.1 on PyPI"