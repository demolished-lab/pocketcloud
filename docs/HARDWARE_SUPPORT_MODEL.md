# Hardware Support and Emulation Model

**Status:** Scope contract and test-preparation guidance. It does not claim support for any specific phone or laptop beyond the CI evidence recorded in `BUILD_STATUS.md`.

## What “support” means

PocketCloud will declare support only for an explicit device-and-software tuple: device make/model, hardware revision when discoverable, OS/build/API, runtime/distribution versions, and the PocketCloud revision tested. Unknown hardware is not silently treated as equivalent. A profile records observations and their sources; it does not infer unobserved firmware, sensors, power behavior, GPU drivers, or OEM policy.

“Exact emulation of every hardware” is not a feasible acceptance target. Hardware families have model-specific CPUs, memory maps, interrupt controllers, peripherals, firmware, sensors, radios, power management, and vendor changes. Emulators model selected machines and selected device behavior. They do not reproduce every device, timing effect, OEM modification, physical sensor, thermal path, or electrical property. QEMU's ARM guide explains that its many board models still cover only a small fraction of the ARM ecosystem and that OS images can be board-specific [1]. Android Virtual Devices provide configurable hardware profiles and system images for testing Android behavior, not a bit-for-bit reproduction of every retail phone [2].

## Evidence levels

1. **Contract tests and mocks** validate PocketCloud logic against explicit inputs. They are required for deterministic boundaries, stale or missing signals, failures, and state transitions. They prove software behavior under the supplied fixture only.
2. **Virtual-device tests** use a named Android AVD or a named QEMU machine/image. Record the emulator version, virtual hardware profile/machine, system image, host OS and configuration. These tests are useful for API, install, and repeatable software checks. They do not prove OEM lifecycle behavior, physical sensors, battery drain, thermal response, radio conditions, or the target laptop GPU.
3. **Hardware-in-the-loop tests** use the actual named phone and laptop. This is the required evidence for a device support claim involving Termux, Android background restrictions, physical thermal/battery behavior, Windows drivers, GPU availability, sleep/wake, and real LAN pairing. Record setup and recovery results. A CI runner or emulator cannot substitute for this evidence.

A test report must name its evidence level. Synthetic input, a virtual device, and hosted Windows CI must never be relabeled as physical-target verification.

## REA integration boundary

[morluto/rea](https://github.com/morluto/rea) can be used as an optional development/research tool to inspect authorized app artifacts, binaries, firmware, or connected Android devices and collect evidence through the caller's ADB installation [3] [4]. REA's device guide says it does not start or manage emulators and does not install Android platform-tools; it is an inspection workflow, not an emulator or hardware abstraction layer [4]. Its code is MIT-licensed, but third-party tools and components retain their own terms [5].

REA must not become a PocketCloud runtime dependency or a required network/service. Use it only in an isolated development profile, with an explicit target, an authorized analysis scope, and review of its tool effects and third-party licenses. Its observed values may inform a device profile, but cannot prove behavior that was not measured.

## First PocketCloud target

The initial test target remains the user-specified unrooted Android phone and Windows 11 laptop. The engineering brief provides laptop hardware specifications but does not identify the actual model/build or runtime GPU/driver state. Phone model, Android/API version, RAM/storage, chipset, Termux build, and OEM restrictions remain unknown. Do not select universal resource thresholds or claim a compatibility matrix until these are recorded.

Use the read-only [Android target preflight](../scripts/testing/target_preflight.py) before the first phone test. It gathers a local inventory through ADB, selects exactly one authorized device, omits the ADB serial from its report, and reports missing values instead of guessing. Its output is **inventory only**. It does not test the PocketCloud service, Termux `RUN_COMMAND`, user permission settings, lifecycle, pairing, thermal behavior, or release criteria. The Windows laptop still requires a separate target inventory of exact Windows build, CPU, RAM, storage, GPU, driver/runtime and sleep state.

## Acceptance rules

A new hardware target is added only after its profile, capability differences, required test list, and recovery path are documented. Shared code may support several devices when they satisfy the same tested contract; this is compatibility through verified behavior, not exact emulation. Unknown or unavailable hardware signals remain explicit states. When target behavior cannot be reproduced virtually, the acceptance test must use the physical target or remain open.

## References

[1]: https://www.qemu.org/docs/master/system/target-arm.html "QEMU Arm system emulator and board support"
[2]: https://developer.android.com/studio/run/managing-avds "Android Virtual Device configuration"
[3]: https://github.com/morluto/rea "REA project overview"
[4]: https://github.com/morluto/rea/blob/main/docs/adb-device-analysis.md "REA ADB device-analysis guide"
[5]: https://raw.githubusercontent.com/morluto/rea/main/LICENSE "REA MIT license"
