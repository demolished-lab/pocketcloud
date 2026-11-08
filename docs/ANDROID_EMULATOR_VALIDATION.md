# Android Emulator Validation

**Purpose:** Add repeatable Android-framework evidence for the native supervisor while keeping physical-device gates separate. This document describes virtual-device testing only; it does not claim Stage 2 hardware acceptance.

## Current test design

The AVD test runner uses named Android Virtual Devices built from Google APIs x86_64 system images, with the `pixel_2` hardware profile at API 29 and API 36. API 29 exercises a pre-Android-14 runtime path; API 36 exercises the current target API and `specialUse` service metadata. The instrumented tests launch the installed app, verify the visible start/stop/pairing controls, and inspect the package manager's installed service and permission metadata. Test dependencies are pinned to AndroidX Test Runner 1.7.0 and ext-JUnit 1.3.0, listed as stable releases in the official AndroidX Test notes [5].

The GitHub Actions workflow is configured to run `connectedDebugAndroidTest` on Linux after booting each emulator with KVM VM acceleration. The first hosted attempt (run 42480430274) confirmed KVM but failed before either AVD booted because QEMU could not load `libpulse.so.0`. The workflow now installs Ubuntu's `libpulse0` package, which provides that shared library on Noble [7]; the rerun is pending. The workflow checks the reported API and `ro.kernel.qemu` property before accepting the device as an AVD. Those fields identify the test environment; they do not identify a physical phone or measure hardware fidelity. GitHub documents Android emulator acceleration on hosted Linux runners [4] and its KVM setup procedure [6].

## Reproduction

Install JDK 17 and Android SDK command-line tools, accept the SDK licenses interactively, then install the SDK components and run one supported profile. On Ubuntu 24.04, install `libpulse0` for the emulator's QEMU runtime [7]:

```sh
sudo apt-get install --no-install-recommends --yes libpulse0
sdkmanager --install \
  "platform-tools" "emulator" "platforms;android-36" "build-tools;36.0.0" \
  "system-images;android-29;google_apis;x86_64" \
  "system-images;android-36;google_apis;x86_64"
POCKETCLOUD_AVD_API_LEVEL=36 scripts/testing/run_android_emulator_tests.sh
```

Set `POCKETCLOUD_AVD_API_LEVEL=29` to run the older profile. The test runner requires a host where Android Emulator VM acceleration is available; it checks acceleration and fails clearly rather than silently switching to a slow or different execution mode. Use `./gradlew testDebugUnitTest` separately for local JVM tests.

## Evidence boundary

A passing AVD run proves only the tested APK, Android API image, virtual hardware profile, host configuration, and test cases. It does not test the user's actual Termux installation, manually granted `RUN_COMMAND` permission, external-command allowlist, Termux callback behavior, camera/QR operation, OEM background policy, physical battery/thermal behavior, actual sensors, Windows laptop GPU, or phone-to-laptop LAN pairing. The Stage 2 physical phone/laptop gates remain open, and Stage 3 resource-policy implementation remains blocked on the actual phone lifecycle gate.

Android documents instrumented tests as running on physical or emulated Android devices and describes AVDs as configurable virtual devices for Android version and hardware-profile testing [1] [2]. Its emulator acceleration guidance requires host virtualization support, and GitHub documents hardware acceleration on its hosted Linux runners [3] [4].

## References

[1]: https://developer.android.com/training/testing/instrumented-tests "Android instrumented tests"
[2]: https://developer.android.com/studio/run/emulator "Run apps on the Android Emulator"
[3]: https://developer.android.com/studio/run/emulator-acceleration "Configure hardware acceleration for the Android Emulator"
[4]: https://docs.github.com/en/actions/reference/runners/github-hosted-runners "GitHub-hosted runners"
[5]: https://developer.android.com/jetpack/androidx/releases/test "AndroidX Test release notes"
[6]: https://github.blog/changelog/2024-04-02-github-actions-hardware-accelerated-android-virtualization-now-available/ "GitHub Actions Android virtualization announcement"
[7]: https://packages.ubuntu.com/noble/amd64/libpulse0/filelist "Ubuntu Noble libpulse0 file list"
