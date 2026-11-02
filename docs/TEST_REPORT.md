# Stage 1 Test Report

**Run date:** 2026-11-02. **Environment:** Linux x86_64 Manus sandbox, Python 3.12.3, execution UID 1000; isolated virtual environment with `requirements.lock` installed. These are host results, not Android or Windows results.

## Automated checks

Command: `PYTHONPATH=runtime .venv/bin/python -m unittest discover -s tests -v`

Result: **10 tests passed** in 17.343 seconds on the recorded run. The suite verifies liveness/readiness; durable job completion and idempotency across restart; conflict rejection for a changed payload; interrupted-job quarantine; strict handler allowlisting; 8 KiB request-body rejection; root refusal; rejection of state outside the user's home; exclusive single-instance locking; concurrent submissions checked against updated storage usage; rejection at database-size and free-space thresholds without a row being written; SQLite WAL/foreign-key/busy-timeout/synchronous FULL and `max_page_count`; and private POSIX directory/database modes.

Additional final checks passed: `PYTHONPATH=runtime .venv/bin/python -m compileall -q runtime tests`; `.venv/bin/python -m pip check` (“No broken requirements found”); and `bash -n scripts/termux/run.sh`.

## Interpretation and remaining gate

The suite starts the service through `scripts/termux/run.sh` using Linux Bash under non-root UID 1000. It demonstrates rootless Linux process execution, private-home storage controls, exclusive ownership, and durable local state on this host. It does not establish Termux package installation, Android foreground-service eligibility, notifications, Doze/background behavior, OEM battery restrictions, Android process death/reboot recovery, or the `RUN_COMMAND` bridge.

Database admission is serialized through this bounded Stage 1 handler lifecycle, and SQLite page limits are applied to application/migration connections. The free-space check is point-in-time; unrelated applications can consume disk after admission. Runtime requires local app-private storage but cannot reliably identify every filesystem/mount type. Do not use a network/shared filesystem.

No Windows hardware, GPU driver, CUDA, sleep-state, or worker test was performed. Pairing, LAN dispatch, backup/restore, dashboard behavior, corruption/failure injection, and soak durations remain unrun. No automatic retention/pruning is implemented; storage pressure rejects new jobs instead of deleting existing state.