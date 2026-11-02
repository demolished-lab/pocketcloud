# Stage 2 and Runtime Hardening Audit

**Audit date:** 2026-11-02
**Scope:** Existing Stage 1 runtime and Stage 2 Android supervisor/pairing-host source, compared with the PocketCloud Engineering Master Prompt v2 and repository security requirements.
**Evidence boundary:** Linux sandbox tests only for the changes below. No Android phone or Windows laptop is attached; no device gate is closed by this audit.

## Findings and dispositions

| Finding | Specification concern | Change | Verification |
|---|---|---|---|
| The Termux `stop` verb could return exit code 0 when a recorded PID was alive but ownership checks did not confirm it was PocketCloud. | Fail-safe ambiguous outcomes; the Android service may remove its visible Stop control only after a successful Termux result. | A live unconfirmed PID now produces a nonzero result, is not signalled, and retains its PID record. Only a dead PID is treated as stale and cleaned. | `test_termux_stop_does_not_report_success_for_unowned_live_pid` plus the full runtime integration suite. |
| The runtime accepted the user's home directory itself as `POCKETCLOUD_DATA_DIR`, allowing recursive private-mode changes on the home directory. | State must use private app storage; path safety and permission changes must be constrained. | Resolved home-equality is rejected before state-directory creation or chmod. | `test_home_directory_cannot_be_used_as_runtime_state` checks both settings and preparation paths and verifies the mode is unchanged. |
| Python's default JSON decoder silently accepted duplicate request keys, including nested payload keys. | Strict input validation requires unambiguous schemas. | Runtime parsing now uses a duplicate-detecting object-pairs hook at every nesting level; malformed/duplicate documents return 422 and persist nothing. | `test_duplicate_json_keys_are_rejected_without_persistence`. |
| Pairing had no persistent record of operator approval/denial decisions. | The engineering prompt requires pairing audit history; audit records must be bounded and redact credentials. | The laptop appends only cryptographically verified grant/denial decisions to `pairing-audit.jsonl`: UTC time, pairing ID, verified phone ID, and key fingerprint. The log is capped at 1 MiB, mode 0600 on POSIX (Windows ACL inherited), excludes tokens/signatures/keys/phone labels/source addresses, and audit-write failure prevents trust-key persistence. HTTP access logging remains disabled. | Pairing-host tests verify grant/denial recording, no secret leakage, POSIX mode, and size-cap fail-closed behavior. |

## Verification summary

- Runtime: **20 tests passed** on Linux x86_64 / CPython 3.12.3, in 22.617 seconds.
- Pairing host: **17 tests passed** on Linux / CPython 3.12, in 0.194 seconds.
- Existing hosted CI evidence for the repository predates these changes. The new pairing audit tests have not yet been re-run on hosted Windows CI at the time this report was written.
- Existing project evidence remains relevant but separate: hosted Android compilation/unit tests, Termux package-index wheel resolution, and a 15-minute Linux runtime soak do not prove target-device behavior.

## Remaining gaps and explicit non-claims

This is not a Stage 2 completion report. Physical Termux behavior, Android foreground-service/Doze/OEM lifecycle, actual phone-to-Windows pairing, Windows laptop operation, revocation/key rotation, persistent authenticated sessions, broader audit events, backup/restore, longer soaks, and independent security review remain open. The pairing audit records operator approval decisions only; it does not record malformed unauthenticated requests and does not implement revocation or later-stage dispatch/result/policy audit events. The phone and laptop target hardware remain unverified.
