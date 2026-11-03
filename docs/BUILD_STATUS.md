# Build Status — Stage 2 Source Implemented; Device Gates Open

**Current phase:** Stage 1 host safeguards and the Stage 2 Android/laptop pairing foundation are implemented in the public repository. The latest hardening source and pinned CI workflow passed local regressions and all five hosted jobs in [GitHub Actions run 41660601371](https://github.com/demolished-lab/pocketcloud/actions/runs/41660601371) on commit `a67f02a`. No target-device gate has passed: the Android phone and Windows laptop remain unattached.

## Stage 1 runtime

The loopback runtime uses Starlette, Uvicorn and SQLAlchemy; project-owned SQLite migrations are immutable and SHA-256 checked. It provides liveness/readiness, WAL/foreign keys/busy timeout/synchronous FULL, durable job/event rows, an 8 KiB request cap, strict request validation, the harmless registered `self_test.v1` handler, idempotency, structured bounded logs, and quarantine of unfinished jobs as `needs_reconciliation`.

It refuses root, restricts state to a dedicated child of the user's home, fails closed on private storage/ownership checks, uses an exclusive runtime lock, rejects new work at database/free-space limits, and never auto-deletes state. Host fault injection covers invalid database headers and SQLite page corruption. Free-space remains a point-in-time guard; filesystem identity, backup/restore, power-loss recovery, target-filesystem behavior and longer soaks remain open.

The latest Linux sandbox run passed **20 runtime integration tests** in 23.808 seconds. It verifies duplicate-key JSON rejection, home-directory state-path rejection without permission mutation, unrelated-live-PID stop refusal and PID-record preservation, plus corruption, concurrency, traversal and symlink controls. Compile, `pip check`, shell syntax and Termux lock checks passed. A **15-minute Linux host soak passed**: 180 readiness/idempotency cycles, zero failures, 361 request-latency samples (p50 3.13 ms, p95 5.01 ms), RSS 52,628–52,684 KiB, and an unchanged 36,864-byte database. This remains host-only evidence, not a phone or long-duration reliability test. A fresh binary-only Android arm64 CPython 3.12 wheel resolution passed for all eight runtime lock packages; it is package-index evidence, not an actual Termux installation.

## Stage 2 pairing host

`pairing_host/` implements a same-LAN, short-lived HTTPS bootstrap endpoint only: a one-use QR invitation, P-256 TLS identity/pin, strict signed transcript verification, explicit laptop approval, public-key-only storage, generic wire errors and no command/job API. It also appends cryptographically verified operator grant/denial decisions to a private, sanitized JSONL audit file capped at 1 MiB; HTTP access logs remain disabled. The phone's colon-separated SPKI fingerprint and laptop console now use the same human-comparable representation.

**17 pairing-host tests passed** in a disposable Linux CPython 3.12 environment in 0.200 seconds. The current pairing suite also passed on the hosted Windows 2025 runner in CI run 41660601371. Coverage includes bounded/private audit storage and secret redaction, replay, concurrent one-use, duplicate JSON key, corrupt-store fail-closed, denial, invalid signature/key, exact-interface binding, shared Unicode-name policy, and a slow TLS-client regression. The HTTPS listener refuses wildcard binds, caps handlers at eight, and performs the five-second TLS handshake/header/body deadlines inside bounded workers. Host tests do not establish behavior on the user's laptop, Android interoperability, or a security assessment.

## Stage 2 Android supervisor

`android-supervisor/` contains a native Java Android app source targeting API 36/minimum API 24, with a user-started `specialUse` foreground service, no boot start, strict invitation parser, Android Keystore P-256 phone identity, pinned HTTPS client, and fixed-argv Termux `RUN_COMMAND` boundary. Its one-shot Termux result callback requires Termux 0.109+ and keeps Stop visible until a successful stop exit result arrives. Termux's external-command permission is manually granted in PocketCloud app settings. Eight Java/JUnit tests are present.

Local command `./gradlew --no-daemon testDebugUnitTest` was attempted and **failed before tests or compilation** because this sandbox has no Android SDK/`ANDROID_HOME`; the environment has a Java runtime but no `javac`. The latest pinned hosted CI job passed Android unit tests and `assembleDebug`, and uploaded a debug APK. An earlier run's downloaded APK was 365,215 bytes and passed ZIP integrity validation with SHA-256 `04af6e3e96722c1520d299c855ea800a15da2184dd2792ce0b7021b835d19a7a`; this earlier artifact is not represented as the output of the latest run. Google Play eligibility of the `specialUse` use case and all device behavior remain unresolved.

## CI and remaining gates

The [latest GitHub Actions run](https://github.com/demolished-lab/pocketcloud/actions/runs/41660601371) for commit `a67f02a` passed all five jobs: Linux runtime, Termux Android-wheel resolution, Android build/unit tests and debug APK upload, pairing-host Linux, and hosted Windows pairing-host tests. All actions are pinned to full commit SHAs with release comments. Runners are explicitly `ubuntu-24.04` and `windows-2025`. Weekly Dependabot updates are configured for GitHub Actions. Hosted Windows results do not substitute for the user's laptop.

No Android phone or Windows laptop is attached. APK install, actual Termux permission/service calls, lifecycle/Doze/OEM behavior, same-LAN phone/laptop pairing, Windows laptop operation, backup/restore, revocation/rotation, filesystem-specific failure behavior, independent security review, and 1/6/12/24-hour soaks are incomplete. The Stage 1 and Stage 2 hardware gates remain **not proven on target hardware**. Stage 3 resource protection is preparation-only; see `STAGE_3_PLAN.md`.

The public repository's project license is MIT. `THIRD_PARTY_NOTICES.md` records the current direct and relevant transitive dependency licenses; a complete resolved APK license report is still required before release.
