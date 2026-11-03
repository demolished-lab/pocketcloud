# Stage 3 — Resource Protection Plan

**Status:** Preparation only; Stage 3 implementation has not started. Stage 2's real-device lifecycle gate remains open because no target Android phone is attached. This plan does not mark Stage 2 or Stage 3 complete, and it does not authorize treating simulated signals as device evidence.

## Purpose and boundary

Stage 3 will protect the phone from optional PocketCloud work when system conditions become unsafe. It is not an operating-system thermal governor, a battery-health guarantee, or a mechanism for overriding Android's process and power-management decisions. The current runtime has only the small deterministic `self_test.v1` handler; it has no sustained optional workload to yield. A later implementation must define a cancellable/cooperative test workload before claiming the Stage 3 pause/resume gate.

No numerical battery, memory, or thermal thresholds are selected in this plan. Thresholds and recovery delays require a named target phone, supported Android API, and observed behavior. Do not infer per-app use or sensitive user activity. Any future policy applies only to PocketCloud's optional work.

## Signal contract

The Android adapter should collect only system-level signals and attach source, observation time, runtime/API availability, and freshness to each value. The internal state must distinguish a measured value from `unavailable`, `permission_denied`, `stale`, and `estimated`; missing data must never be silently converted to a healthy reading.

- **Thermal:** use `PowerManager` thermal status and its change listener where the target OS exposes them. Thermal headroom is optional. Android documents that headroom can be unsupported (`NaN`), is based on slow-moving sensors, and gains no benefit from calls more often than about once per second; substantially faster calls may themselves result in `NaN`. Treat unknown or unsupported values as unavailable, not zero [1].
- **Memory:** use `ActivityManager.getMemoryInfo` for system-level available-memory and low-memory status. `availMem` is not an absolute measure of how much memory can safely be consumed, so do not turn it into an unsupported hard capacity claim. Do not inspect unrelated apps' private memory or process state [2].
- **Battery and charging:** obtain the current charge/charging state from the sticky `ACTION_BATTERY_CHANGED` information and react to power connection changes rather than continuously polling. Android warns that continually monitoring battery level can consume more battery than the work being managed; future sampling must remain event-driven or demonstrably low-impact [3].

The adapter must check each API at runtime and work safely when a signal or service is absent. It must not require root, hidden APIs, or privileged device access.

## Policy behavior to implement after the gate

The policy core should be a pure, deterministic component that receives timestamped snapshots and returns a bounded decision for optional work: allow, reduce admission, or pause. Every restrictive decision should include a stable reason code, the triggering signal/provenance, and the condition required before resumption.

The intended state vocabulary is `active`, `adaptive`, `charging`, `critical`, and `recovery`. These names are design labels, not configured device thresholds. Critical signals should stop new optional admissions immediately and request cooperative yielding from any eligible running optional task. Resumption should require valid, fresh recovery signals that remain safe for a measured dwell period; it must not oscillate as readings cross one boundary. A missing/stale critical input must not be treated as evidence that the device is safe. No task should be killed without an explicit, documented cancellation contract.

Policy evaluation should be triggered by system events and bounded timers, not high-frequency polling. Store timestamps with a monotonic clock for freshness and dwell calculations; use wall-clock timestamps only for human-readable records.

## Host verification and device gate

Before Android integration, the pure policy component should have deterministic tests for each state transition, boundary values, stale and missing inputs, unsupported sensors, contradictory signals, hysteresis/dwell, immediate stop-admission, delayed resumption, event ordering, and repeated/duplicate events. Tests should prove that unavailable data never becomes a fabricated normal value and that every pause has an operator-readable reason.

After Stage 2 passes on the target phone, validate the adapter and cooperative workload on that exact Android build and Termux version. The matrix should include screen-off and background intervals, battery saver, Doze/idle, power connect/disconnect, low-battery conditions, memory pressure, thermal-status changes, sensor unavailability, service/process interruption, and recovery. Record device model/build, API level, Termux version, setup, timestamps, signal provenance, logs with secrets redacted, observed yields/resumes, and user-visible impact. Emulator or synthetic-signal tests are software evidence only; they do not close the device gate.

Stage 3 exits only when an actual optional workload pauses safely under observed critical conditions, recovery follows the documented dwell policy, missing signals fail conservatively, and the phone remains responsive. If no meaningful safe stress condition can be produced on the target device, document that limitation rather than claiming proof.

## Inputs required before implementation

The next device audit needs the phone manufacturer/model, Android version/API level, Termux distribution/version, and confirmation that the device may be used for controlled lifecycle/resource tests. Preserve the Windows laptop as a separate later-stage target; hosted Windows CI is not its substitute.

## References

[1]: https://developer.android.com/reference/android/os/PowerManager "Android PowerManager API reference"
[2]: https://developer.android.com/reference/android/app/ActivityManager.MemoryInfo "Android ActivityManager.MemoryInfo API reference"
[3]: https://developer.android.com/training/monitoring-device-state/battery-monitoring "Android battery monitoring guide"
