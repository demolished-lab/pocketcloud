# Technical Requirements Document

## Runtime topology

The phone is intended to be the single logical authority for desired state and assignment. The first external worker target is a Windows laptop. Current implementation remains a loopback-only phone-side runtime foundation; there is no worker dispatch, LAN API, dashboard, or production distributed execution. Later worker processes may buffer already-authorized work/results during disconnects but must not assign new phone-owned jobs.

## Stage 1 dependency decision and Android compatibility

Stage 1 runtime direct pins are Starlette 1.10.0, Uvicorn 0.54.0, and SQLAlchemy 2.1.6. Their resolved lock contains eight packages including pure-Python transport/support dependencies. The old FastAPI/Pydantic/Pydantic-Core path was removed after the selected Pydantic Core release had no matching Android arm64 CPython wheel. Alembic/Mako/MarkupSafe were also removed; Stage 1 now applies project-owned checksummed SQLite SQL migrations, refusing gaps, changed applied migrations, or a schema newer than the runtime. The application dependencies no longer contain the identified compiled wheel blockers.

Evidence: a clean temporary environment resolved all `requirements.in` dependencies; a binary-only `pip download` using `--platform android_24_arm64_v8a --python-version 312 --implementation cp --abi cp312 --only-binary=:all:` succeeded for every exact package in `requirements-termux.lock`. The downloaded wheel set contains eight packages; SQLAlchemy resolves to its `py3-none-any` wheel for this Android target. GitHub Actions repeats this check. This is Android wheel-tag/package-index evidence, not a Termux install or target-phone proof. Actual Termux Python version, installed tags, filesystem/permission behavior, Android service lifecycle and OEM power management remain unverified.

Python 3.11 or later is the declared floor. The Linux `requirements.lock` is an exact pin set, not a claim that Linux wheels run on Android. The Android-specific lock is separately resolved and should be refreshed if the Python version, PEP 738 tag, or direct requirements change. Runtime operation makes no network calls after dependencies are installed.

## Stage 1 data and API controls

The local service binds only to loopback, refuses UID 0, and requires its data path to be a dedicated child of the current user's home; the home directory itself is rejected before any permission mutation. It verifies owner/private POSIX modes for state, DB and runtime lock, and acquires an advisory single-process lock before schema migration or recovery. Runtime JSON rejects duplicate keys at every nesting level. Operators must select local app-private storage; the runtime cannot reliably identify every filesystem or network mount.

The API has strict hand-validated request schemas, bounded request bodies, a single harmless registered handler (`self_test.v1`), idempotency, durable state transitions, and truthful liveness/readiness endpoints. SQLite uses WAL, foreign keys, a 10-second busy timeout, synchronous FULL, and `max_page_count` derived from the DB ceiling. Capacity checks include the database and WAL/SHM sidecars plus a conservative write estimate; admission and the bounded handler lifecycle are serialized. Defaults are a 64 MiB DB ceiling and 8 MiB free-space reserve. Free-space remains a point-in-time check. No active/unresolved jobs are automatically pruned; backup/restore and retention remain future work.

## Android supervisor and pairing bootstrap

The native supervisor is an explicit, user-started FGS foundation. It calls only the declared Termux `RUN_COMMAND` service and a fixed repository-owned script with allowlisted `start`, `stop`, or `status` verbs. Termux 0.109+ one-shot result callbacks are required for outcome reporting; the foreground Stop notification is removed only when the callback confirms exit code zero. Missing callback after 30 seconds is reported as unconfirmed, not success. A live PID not proven to belong to PocketCloud returns nonzero and its PID record is preserved; only a confirmed stale/dead record is cleaned. The Termux script rejects traversal and symlinked state-path components before filesystem mutation. It does not accept shell commands from QR/network input. Android 14+ `specialUse` declaration and Play review are policy-sensitive; the repository does not claim distribution approval. No boot receiver or uptime guarantee is permitted by this design.

The pairing bootstrap is specified in `docs/PAIRING_PROTOCOL.md`: a five-minute one-use QR token, local numeric private/ULA IP, TLS certificate SPKI pin, Android Keystore P-256 phone proof-of-possession, printable-name validation shared across Android/Python, and explicit approval on both devices. The laptop HTTPS listener binds only the advertised interface, caps at eight workers, and applies a five-second TLS-handshake/header/body timeout inside worker threads. The host records verified approval decisions in a bounded, sanitized local audit file; malformed requests and HTTP access details are not logged. No remote job/command API is part of Stage 2 pairing. Security review, revocation UI, persistent authenticated sessions, key recovery and real same-LAN phone/laptop validation remain open gates.

## Runtime dependency policy

Before adding a package, record exact version, license, maintenance state, Python/OS support, footprint, and offline behavior. Pin transitive dependencies; use platform-specific binary-wheel checks where appropriate. Avoid dependencies that require accounts, API keys, telemetry, hosted execution or mandatory online operation. Add hashes, update/rollback guidance and advisory review before release.

## Security boundaries

Private keys are generated on-device and stored using platform facilities where feasible. Pairing uses established ECDSA/TLS mechanisms and explicit pinned identity; no custom cryptographic algorithm is introduced. Discovery is unauthenticated hinting only. There is no remote shell endpoint. Workload directories do not constitute a secure sandbox; PRoot is not a VM or isolation boundary.

## Repository areas

- `runtime/pocketcloud`: Stage 1 loopback API, config, SQLite, jobs and approved handler.
- `runtime/pocketcloud/migrations`: checksummed SQLite SQL schema versions.
- `scripts/termux`: rootless manual launcher and fixed-verb supervisor control script.
- `android-supervisor`: native Android foreground-service and pairing client, subject to build/device gates.
- `pairing_host`: laptop HTTPS pairing/bootstrap host; no worker execution API.
- `tests`, `scripts/testing`, `docs`: automated host evidence, bounded soak harness, specifications and test records.

## References

1. [Starlette 1.10.0 on PyPI](https://pypi.org/project/starlette/1.10.0/).
2. [Uvicorn 0.54.0 on PyPI](https://pypi.org/project/uvicorn/0.54.0/).
3. [SQLAlchemy 2.1.6 on PyPI](https://pypi.org/project/SQLAlchemy/2.1.6/).
4. [PEP 738: Android platform support and wheel tags](https://peps.python.org/pep-0738/).
5. Android, [Foreground-service types](https://developer.android.com/develop/background-work/services/fgs/service-types).
6. Termux, [RUN_COMMAND Intent](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent).
7. Android, [Keystore system](https://developer.android.com/privacy-and-security/keystore).
8. [PocketCloud Pairing Protocol v1](PAIRING_PROTOCOL.md).
