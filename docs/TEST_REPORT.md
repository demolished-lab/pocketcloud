# Stage 1 and Stage 2 Host Test Report

**Run date:** 2026-11-02. Runtime evidence: Linux x86_64 sandbox, CPython 3.12.3, execution UID 1000, `.venv` installed from `requirements.lock`. Pairing-host evidence: Linux sandbox, CPython 3.12, temporary environment installed from `requirements-pairing.lock`. These are host results, not Android or Windows device results.

## Stage 1 runtime suite

Command:

```sh
PYTHONPATH=runtime .venv/bin/python -m unittest discover -s tests -v
```

Result: **17 tests passed** in 17.912 seconds. Coverage includes liveness/readiness; job persistence and idempotency across restart; changed-payload conflict; interrupted-job quarantine; invalid handler/schema and oversized body; root and out-of-home refusal; single-instance ownership; concurrent capacity admission; 24 parallel identical idempotency submissions producing one persisted job; immutable/checksummed migration replay/tampering rejection; SQLite WAL/foreign-key/busy-timeout/synchronous FULL/page-count; injected page corruption detected by `PRAGMA quick_check`; corrupt database header rejected without changing damaged bytes; fixed supervisor verbs; and final/parent-symlink, `..` traversal, and PID/temp/log symlink rejection before writing through state paths.

Additional checks passed:

```sh
PYTHONPATH=runtime .venv/bin/python -m compileall -q runtime tests scripts/testing/soak_runtime.py
.venv/bin/python -m pip check
bash -n scripts/termux/run.sh scripts/termux/supervisor.sh
```

## Stage 2 laptop pairing-host suite

Command, after installing the exact pairing lock into a disposable venv:

```sh
python -m unittest discover -s pairing_host/tests -v
```

Result: **16 tests passed** in 0.192 seconds. Coverage includes exact success schema and public-key-only storage; invalid signatures, curves and DER; expiry; replay; denial consumption; strict/oversized payloads; duplicate JSON keys; concurrent one-use handling; duplicate identity; corrupt-store fail-closed behavior; private/public address policy; exact-interface binding with wildcard rejection; TLS SAN/invitation contract; shared bidi/Unicode-separator rejection; and a slow TLS handshake test proving another request can proceed in a separate bounded worker. The live listener caps eight workers and applies handshake/header/body timeouts. `compileall` and CLI help checks also passed. These tests do not prove Windows file/ACL behavior, physical LAN behavior, Android interoperability, or security assurance.

## Android dependency resolution evidence

A fresh binary-only package-index resolution succeeded for all eight versions in `requirements-termux.lock` using Android arm64 CPython 3.12 tags:

```sh
python -m pip download --dest /tmp/pocketcloud-termux-wheelhouse \
  --requirement requirements-termux.lock \
  --platform android_24_arm64_v8a --python-version 312 \
  --implementation cp --abi cp312 --only-binary=:all:
```

The selected set includes Starlette 1.10.0, Uvicorn 0.54.0, SQLAlchemy 2.1.6 and five support packages. This remains package-index evidence only; it does **not** prove actual Termux Python tags, installation, Android filesystem permissions, service behavior, or device power characteristics.

## Android source build attempt

The Android module contains eight Java/JUnit tests, including bidi/Unicode-name rejection and canonical base64url vectors. Local command `./gradlew --no-daemon testDebugUnitTest` was attempted. Gradle stopped before test execution or source compilation with `SDK location not found`; neither `ANDROID_HOME` nor `ANDROID_SDK_ROOT` is configured, no Android SDK is installed, and the sandbox has a Java runtime but no `javac`. Therefore there is **no Android compilation, unit-test, APK, emulator, or install evidence** from this run. GitHub Actions is configured to run Android unit tests and assemble a debug APK, but those jobs are pending and must be reported separately when executed.

## Bounded soak smoke

`scripts/testing/soak_runtime.py` previously ran with `--duration-seconds 8 --interval-seconds 0.5 --port 8877` and returned **PASS**. It exercised readiness plus repeated idempotent submission of one harmless test job while sampling process RSS, database bytes, free space and latency. This is an eight-second smoke test only, not a reliability soak; 1/6/12/24-hour runs remain open.

## Interpretation and remaining gates

The suites demonstrate Linux sandbox behavior with fresh dependency environments. They do not establish Termux installation, Android foreground-service eligibility, notifications, Doze/background behavior, OEM battery restrictions, Android process death/reboot recovery, or actual `RUN_COMMAND` behavior. The supervisor script test invokes the Termux-facing shell locally on Linux and is not a phone test.

No Windows hardware, GPU driver, CUDA, sleep-state, or actual-laptop validation was performed. Hosted Windows CI is configured but not yet run and would not prove the user's laptop. Phone-to-laptop pairing requires same-LAN physical-device validation and independent security review. Backup/restore, power-loss recovery, revocation/rotation, filesystem-specific crash tests and long soaks remain open. The free-space check is point-in-time; no automatic retention/pruning is implemented.
