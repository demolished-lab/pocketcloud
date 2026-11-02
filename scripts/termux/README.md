# Termux Stage 1 runtime and Stage 2 supervisor control

The runtime and shell supervisor are rootless controls, not an Android uptime guarantee. They do not register boot auto-start, disable battery optimization, or claim immunity from Doze, force-stop, OEM process limits, or phone restart.

## Manual Stage 1 setup

From a trusted Termux installation, install the Termux Python package (`pkg install python`, Python 3.11 or later), clone the repository inside Termux's private home, then install the Android-specific exact lock:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements-termux.lock
PYTHON_BIN="$PWD/.venv/bin/python" ./scripts/termux/run.sh
```

Keep the checkout and SQLite data in local app-private Termux storage. Default data is `~/.local/share/pocketcloud`; `POCKETCLOUD_DATA_DIR` may select another path only under the Termux home. The launcher rejects `..` traversal and symlinks in every existing path component before creating/chmodding the state directory; it also refuses symlinked PID/temp/log files. Use local storage, not shared/external storage or a network filesystem; the runtime cannot reliably identify every filesystem/mount type. The default port is 8765; `POCKETCLOUD_PORT` must be 1024–65535.

The runtime refuses root, verifies ownership/private POSIX permissions for its data directory, DB and runtime lock, and acquires an exclusive lock before migration/recovery. SQLite uses WAL, foreign keys, a 10-second busy timeout, synchronous FULL and a page-count limit. New work is admitted only within the configured database/free-space thresholds; the free-space check is point-in-time. No job state is automatically pruned. The API is loopback-only; do not expose it to LAN peers.

## Fixed-verb supervisor script

The Android app's Termux bridge is deliberately restricted to `scripts/termux/supervisor.sh` with one verb: `start`, `stop`, or `status`. The script launches only `python -m pocketcloud serve` from this checkout, records a private PID file, checks that PID ownership against the checkout working directory/command line, and signals only that process with graceful SIGTERM. It never accepts a command string, path from a QR code, or network-supplied handler. If its ownership check is ambiguous, it does not signal a process. The app uses Termux's documented one-shot result callback; the ongoing Stop notification is removed only after Termux reports a successful stop exit code. If no result arrives within 30 seconds, it reports that the command outcome is unconfirmed and keeps the notification visible.

The script can be exercised manually in Termux:

```sh
./scripts/termux/supervisor.sh start
./scripts/termux/supervisor.sh status
./scripts/termux/supervisor.sh stop
```

For the Android app to invoke it, use a Termux version that supports `RUN_COMMAND` result callbacks (0.109 or later). The user must enable Termux's documented external-app opt-in (`allow-external-apps=true`) and manually grant `com.termux.permission.RUN_COMMAND` to PocketCloud in Android app settings. Do not grant the permission to untrusted apps. If unavailable, manual Termux launch remains the fallback.

The app starts only from a visible user action, shows a foreground-service notification, and offers Stop; it does not start on boot. Android's `specialUse` type and distribution review need platform/policy confirmation. A foreground service improves user visibility but does not guarantee that Android/OEM software keeps the backend alive.

## Compatibility evidence and open gates

`requirements-termux.lock` passed a binary-only Android arm64 CPython 3.12 package-index resolution for the eight locked packages. GitHub Actions repeats that resolver check. This reduces the prior Pydantic/native-build concern, but it is not a Termux package installation, actual Termux Python-tag check, Android build, or phone test. No phone is attached. Validate Termux package sources, `RUN_COMMAND`, private storage, app lifecycle, notifications, Doze, OEM battery behavior and recovery on the exact target phone before relying on this supervisor.
