# PocketCloud

PocketCloud is a local-first personal infrastructure platform. Its intended controller is an unrooted Android phone; the first external worker is a Windows 11 laptop. It is designed around durable state, explicit trust, approved handlers, and transparent resource protection—not virtual machines or guaranteed uptime.

## Current status

The public repository contains the Stage 0 engineering baseline and the first Stage 1 runtime foundation. Stage 1 provides a loopback-only Python API, SQLite/Alembic persistence, health/readiness endpoints, a harmless registered `self_test.v1` handler, idempotency protection, and quarantine for interrupted jobs. It refuses root, restricts state to private user-home storage, protects against duplicate process startup, and enforces configurable SQLite/free-space admission controls. Ten Linux host integration tests pass; see the [Stage 1 test report](docs/TEST_REPORT.md).

This is not the full MVP. There is no native Android supervisor, secure pairing, remote/LAN access, Windows worker, GPU detection, dashboard, agent host, backup/restore, or end-to-end phone-to-laptop execution yet. The target Android phone and Windows laptop are not attached, so no Termux or target-device behavior is claimed as verified.

## Run the Stage 1 runtime

Use Python 3.11 or later. From the repository root, install the pinned dependencies and launch the manual loopback service:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
PYTHON_BIN="$PWD/.venv/bin/python" ./scripts/termux/run.sh
```

The service binds only to `127.0.0.1:8765` by default and stores state under `~/.local/share/pocketcloud`. State paths outside the current user's home are refused; use local private storage, not a network/shared filesystem. The service refuses root and permits only one process to own a data directory. Defaults are a 64 MiB SQLite page/database limit and an 8 MiB minimum free-space admission threshold; adjust with `POCKETCLOUD_MAX_DATABASE_BYTES` and `POCKETCLOUD_MIN_FREE_BYTES`. The free-space check is point-in-time. When a limit is reached, new jobs are rejected; existing state is never auto-deleted.

`GET /livez` reports process liveness; `GET /readyz` checks database readiness. The only accepted job handler is the harmless `self_test.v1`; no shell command or user-supplied code can execute. On startup, unfinished jobs are marked `needs_reconciliation` rather than replayed blindly.

These instructions have been exercised on the non-root Linux sandbox, not on Termux or an Android device. A public repository does not grant a license; no license has been selected.

## Engineering documents

- [Stage 0 feasibility report](docs/STAGE_0_FEASIBILITY.md)
- [Stage 1 plan](docs/STAGE_1_PLAN.md)
- [Build status and evidence](docs/BUILD_STATUS.md)
- [Test report](docs/TEST_REPORT.md)
- [Product requirements](docs/PRD.md)
- [Software requirements](docs/SRS.md)
- [Technical requirements and dependency record](docs/TRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security and threat model](docs/SECURITY_AND_THREAT_MODEL.md)
- [Risk register](docs/RISK_REGISTER.md)
- [Staged validation plan](docs/STAGED_TEST_PLAN.md)
- [Decision log](docs/DECISIONS.md)

## Non-negotiable boundaries

- No root, bootloader unlock, ROM/system modification, exploits, or hidden persistence.
- Do not describe PRoot or a managed process as a VM or security boundary.
- Workers execute registered, approved handlers only; there is no arbitrary remote shell endpoint.
- Persist authoritative state before acknowledging work. Use at-least-once delivery, idempotency, and reconciliation; never promise universal exactly-once execution.
- LAN-first operation must not depend on paid APIs, external cloud, Gmail OTP, or hosted relay.
- Android remains a daily-use device. User activity and OS stability outrank optional computation.
- Stage gates require evidence. Missing hardware or real-device tests remain explicitly incomplete.
