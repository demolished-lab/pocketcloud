# PocketCloud

PocketCloud is a local-first personal infrastructure platform. Its intended controller is an unrooted Android phone; the first external worker target is a Windows laptop. It is designed around durable state, explicit trust, approved handlers, and transparent resource protection—not virtual machines or guaranteed uptime. The repository is licensed under [MIT](LICENSE).

## Current status

Stage 1 provides a loopback-only Python runtime, SQLite durable jobs, strict request validation, a harmless registered `self_test.v1` handler, idempotency, restart quarantine, private user-home storage, single-process ownership and configurable storage admission. The old Pydantic Core dependency path was removed. Twenty Linux sandbox runtime integration tests pass, including duplicate-key JSON rejection, home-directory state-path rejection, unrelated-live-PID stop refusal, concurrent duplicate submissions and injected SQLite corruption. Eight additional mocked ADB preflight tests validate safe profile collection; they do not constitute device tests. A 15-minute Linux host soak completed 180 readiness/idempotency cycles with zero failures; this is host-only evidence, not a device or long-duration reliability claim. A binary-only Android arm64 CPython 3.12 wheel resolution passed for all eight runtime packages; this is package-index evidence, not an actual Termux installation.

Stage 2 source includes the native Android supervisor and same-LAN phone-to-laptop pairing bootstrap. The supervisor is user-started, foreground-visible, and limited to three fixed Termux control verbs; its ongoing notification is removed only after Termux reports a successful stop result. Pairing uses a short-lived one-use QR, TLS public-key pin, Android Keystore identity, and explicit approval on both ends; it exposes no remote shell or job dispatch. The laptop records only cryptographically verified approval grants/denials in a bounded, sanitized local audit file; HTTP access logs remain disabled. Locally, 20 runtime integration tests, eight mocked ADB preflight tests, two fake-SDK AVD-runner tests, and 17 pairing-host tests pass. Source commit `a49fdbc` passed [GitHub Actions run 41669385018](https://github.com/demolished-lab/pocketcloud/actions/runs/41669385018), all five jobs, including the Windows-hosted preflight tests, pairing tests and Android build. An API 29/API 36 Android Emulator instrumentation suite is configured. Run 42480430274 exposed a missing `libpulse.so.0` dependency, which is now installed. Runs 42481499465, 42482243358, and 42482523818 exposed AVD lookup/creation failures. Run 42483022448 stopped before AVD creation because of a malformed diagnostic `printf`; the shell issue is fixed, and two fake-SDK control-flow tests pass without using an actual emulator. A new hosted validation is pending. Actions are pinned to verified full commit SHAs, runner images are explicit, and weekly GitHub Actions dependency updates are configured. No Android phone or Windows laptop device validation is claimed.

The next-stage [Stage 3 resource-protection plan](docs/STAGE_3_PLAN.md) is preparatory only. Stage 2's real-phone lifecycle gate remains open, so there is no resource manager or resource-policy implementation yet. This is not the full MVP: there is no Windows worker, GPU discovery, distributed job dispatch, dashboard, agent host, backup/restore or end-to-end execution. No target hardware behavior is claimed as verified.

## Run the Stage 1 runtime

Use Python 3.11 or later. From the repository root, install the host lock and run the manual loopback service:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
PYTHON_BIN="$PWD/.venv/bin/python" ./scripts/termux/run.sh
```

Termux users should use [`requirements-termux.lock`](requirements-termux.lock), then can run the fixed-verb script with `./scripts/termux/supervisor.sh start|status|stop`. The supervisor is not an uptime guarantee and has not been exercised on an Android phone. See the [Termux guide](scripts/termux/README.md).

The service binds only to `127.0.0.1:8765` by default and stores state under `~/.local/share/pocketcloud`. State paths must be a dedicated child of the current user's home; the home directory itself, external paths and shared/network storage are refused. The service refuses root and permits only one process per data directory. Defaults are a 64 MiB SQLite database limit and an 8 MiB minimum free-space threshold; adjust with `POCKETCLOUD_MAX_DATABASE_BYTES` and `POCKETCLOUD_MIN_FREE_BYTES`. The free-space check is point-in-time. When a limit is reached, new jobs are rejected; existing state is never auto-deleted.

`GET /livez` reports process liveness; `GET /readyz` checks database readiness. Only the harmless `self_test.v1` handler is enabled; no shell command or user-supplied code can execute. On startup, unfinished jobs are marked `needs_reconciliation` rather than replayed blindly.

Before a phone test, collect a read-only Android inventory with caller-installed Android platform-tools: `python3 scripts/testing/target_preflight.py`. It requires exactly one authorized ADB device, or `--serial <serial>` when several are connected. It makes no device install/launch/stop/write/root calls, omits the ADB serial from the report, and never overwrites a requested report file. It exits nonzero if inventory is incomplete or the target is unavailable. This is inventory only, not lifecycle or release verification. See the [preflight tool](scripts/testing/target_preflight.py).

## Engineering documents

- [Stage 0 feasibility report](docs/STAGE_0_FEASIBILITY.md)
- [Stage 1 plan](docs/STAGE_1_PLAN.md)
- [Build status and evidence](docs/BUILD_STATUS.md)
- [Host test report](docs/TEST_REPORT.md)
- [Stage 2 specification audit](docs/STAGE_2_AUDIT.md)
- [Stage 2 platform research](docs/STAGE_2_RESEARCH.md)
- [Stage 3 resource-protection plan](docs/STAGE_3_PLAN.md)
- [Hardware support and emulation model](docs/HARDWARE_SUPPORT_MODEL.md)
- [Android Emulator validation runbook](docs/ANDROID_EMULATOR_VALIDATION.md)
- [Pairing protocol v1](docs/PAIRING_PROTOCOL.md)
- [Android supervisor source and setup](android-supervisor/README.md)
- [Laptop pairing host and setup](pairing_host/README.md)
- [Third-party dependency license inventory](THIRD_PARTY_NOTICES.md)
- [Product requirements](docs/PRD.md)
- [Software requirements](docs/SRS.md)
- [Technical requirements and dependency record](docs/TRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security and threat model](docs/SECURITY_AND_THREAT_MODEL.md)
- [Risk register](docs/RISK_REGISTER.md)
- [Staged validation plan](docs/STAGED_TEST_PLAN.md)
- [Decision log](docs/DECISIONS.md)

## Non-negotiable boundaries

- No root, bootloader unlock, ROM/system modification, exploits, boot persistence, or hidden uptime claims.
- Do not describe PRoot or a managed process as a VM or security boundary.
- Workers execute registered, approved handlers only; there is no arbitrary remote shell endpoint.
- Persist authoritative state before acknowledging work. Use at-least-once delivery, idempotency, and reconciliation; never promise universal exactly-once execution.
- LAN-first operation must not depend on paid APIs, external cloud, Gmail OTP, or hosted relay.
- Android remains a daily-use device. User activity and OS stability outrank optional computation.
- Stage gates require evidence. Missing hardware or real-device tests remain explicitly incomplete.
