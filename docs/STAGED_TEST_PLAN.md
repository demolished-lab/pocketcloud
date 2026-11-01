# Staged Validation Plan

No implementation tests have been run; this plan records future evidence requirements. A command that merely starts a process, a screenshot, or a placeholder response does not prove a product capability.

## Stage gates

0. **Feasibility:** record actual phone/laptop OS, hardware, restrictions, dependency choices, unknowns, and threat boundaries. Gate: facts and unknowns documented.
1. **Rootless runtime:** start backend without root in the intended Termux setup; verify config/logs, live/readiness distinction, a process test, and durable SQLite/job state across restart. Gate: rootless execution and durable state.
2. **Android supervisor:** verify notification, correct service declaration, Termux bridge permissions, stop path, and real-device matrix: locked/off screen, background, battery saver, Doze, network transition, low battery, thermal warning, memory pressure, process death, reboot, update, force-stop and manual restart. Gate: results documented; force-stop limitation is honest.
3. **Resource protection:** inject/observe battery/thermal/memory signal availability and provenance; verify optional work yields safely, explains pause, and resumes only after hysteresis/dwell policy. Gate: no oscillation or user-impacting work.
4. **Cloud core/storage:** state transition, migrations, quotas, backup and actual restore, low-storage rejection, process recovery and failure injection. Gate: recovery evidence and no silent active-state loss.
5. **Secure pairing:** short-lived single-use QR, explicit identity confirmation, mutual authentication/encryption, unauthorized/replay rejection, revocation, rotation and audit. Gate: same-LAN pairing security tests pass.
6. **Windows worker:** runtime OS/Python/GPU/driver/CUDA/available resource/sleep capability probes, approved-handler dispatch, timeout, result persistence and graceful shutdown. Gate: actual reported capabilities match the machine.
7. **Distributed execution:** disconnect/reconnect, worker restart, lease expiry, stale epochs, at-least-once retry, idempotent duplicate protection, result buffer and ambiguous-outcome quarantine. Gate: interruption matrix passes.
8. **Networking:** same-LAN direct without external service; optional VPN adapter behavior; network transition; offline queue; show unavailable remote path honestly. Gate: local operation works without external dependency.
9. **Dashboard:** each visible control maps to real API; compare displayed state to authoritative API/database, inject API error and verify safe/error presentation. Gate: no fake controls or telemetry.
10. **Hardening:** dependency, input, security and regression tests; replay/revocation, fuzz/validation, DB/storage failure. Gate: no unresolved critical/high defects.
11. **Release:** reproducible install, setup/recovery/uninstall, backup/restore, versioning and release notes; full phone-laptop end-to-end proof and practical 1/6/12-hour then 24-hour soak reports. Gate: reproducible demo on actual target hardware.

## Evidence records

For each run capture software revision, exact device/OS/build, setup steps, input conditions, timestamps, logs with secrets redacted, actual outcome, deviations, and recovery result. Distinguish sandbox tests from phone and Windows results. Never substitute a planned test or synthetic signal for real-device evidence.