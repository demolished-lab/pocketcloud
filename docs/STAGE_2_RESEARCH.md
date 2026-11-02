# Stage 2 — Platform Research and Evidence

**Research date:** 2026-11-02. **Scope:** Android supervisor and same-LAN phone-to-laptop pairing foundation. The phone and Windows laptop are not attached, so all target-device behavior remains unverified.

## Findings that affect implementation

Android does not grant an app a permanent-uptime exemption. A foreground service must be user-visible, started from an allowed context, and declare an appropriate service type on Android 14 and later. Android's `specialUse` type is only for a valid use case not covered by another type; its manifest subtype is reviewed for Google Play distribution. PocketCloud's use case and intended distribution channel therefore need product-policy validation; this repository's supervisor is a sideload/development foundation, not a Play approval claim. The app starts only after a visible user action, shows a persistent notification, has no boot-start receiver, and exposes explicit Stop.

Termux's documented `RUN_COMMAND` boundary requires the caller to declare `com.termux.permission.RUN_COMMAND`; the user manually grants it from Android Settings → Apps → PocketCloud → Permissions → Additional permissions. The Termux user must also set `allow-external-apps=true`. The official guide supports a one-shot `PendingIntent` result callback from Termux 0.109+; PocketCloud uses it to check the fixed supervisor script's exit code and will not treat asynchronous dispatch alone as confirmed stop success. PocketCloud calls only a fixed, repository-owned supervisor script with one of three allowlisted verbs (`start`, `stop`, `status`); it does not accept a shell command from a network peer or QR code. The user must review the exact Termux distribution and version because the Android app package and settings may vary.

The old FastAPI 0.162.0 path depended on Pydantic Core 2.50.2. PyPI's release files and a binary-only Android arm64 CPython 3.12 resolution both showed that release had no matching Android wheel. To remove that native/Rust wheel dependency, the local API was changed to Starlette with explicit strict request validation; Alembic/Mako was replaced by checksummed SQL migration files. The resulting dependency set contains only pure-Python wheels in the tested resolution. A `pip download --only-binary=:all:` resolution for `android_24_arm64_v8a`, CPython 3.12 succeeded for all eight locked packages. This is package-index evidence only: Termux's installed Python version/tags, actual install, filesystem permissions, Android lifecycle and device power behavior still require a real phone.

Android Keystore will hold a non-exportable P-256 signing key for phone identity. Pairing uses an expiring one-use QR invitation, TLS with the laptop public-key pin from the invitation, a phone-signed challenge transcript, and explicit approval on both devices. No arbitrary shell or job-dispatch capability is added by pairing. Pairing/revocation and later job protocols are separate from the supervisor's local Termux control.

## Evidence not available here

- No Android SDK/`ANDROID_HOME`, `javac`, ADB, emulator, Android phone, Termux installation, Windows laptop, or Windows shell is available in this sandbox. The local Gradle 8.13 invocation stops before compilation because the SDK is missing.
- The hosted GitHub Actions run on commit `280045c` passed Android unit tests and `assembleDebug`, and uploaded a debug APK. No local APK build, emulator run, or physical-device installation has been performed.
- Android service survival across screen-off, Doze, process death, OEM battery management, reboot, notification denial, and Termux configuration failure is untested.
- Pairing-host tests passed on a hosted Windows runner; that is not evidence from the specified laptop.
- A 15-minute Linux host soak passed with 180 checks and zero failures. No security assessment, 1/6/12/24-hour soak, filesystem-specific crash test, or full power-loss test is claimed.

## References

1. Android, [Foreground service types are required](https://developer.android.com/about/versions/14/changes/fgs-types-required).
2. Android, [Foreground-service background-start restrictions](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start).
3. Android, [Foreground service types](https://developer.android.com/develop/background-work/services/fgs/service-types).
4. Android, [Background task choices](https://developer.android.com/develop/background-work/background-tasks).
5. Android, [Notification permission](https://developer.android.com/develop/ui/compose/notifications/notification-permission).
6. Termux, [RUN_COMMAND Intent](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent).
7. Android, [Keystore system](https://developer.android.com/privacy-and-security/keystore).
8. IETF, [RFC 8446: TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446).
9. Python, [PEP 738: Android platform support and wheel tags](https://peps.python.org/pep-0738/).
10. PyPI, [Pydantic Core 2.50.2 release files](https://pypi.org/project/pydantic_core/2.50.2/).
11. Android, [Android 16 SDK setup](https://developer.android.com/about/versions/16/setup-sdk).
12. Android, [Android Gradle Plugin 8.13 release notes](https://developer.android.com/build/releases/agp-8-13-0-release-notes).
13. Kotlin, [Gradle plugin compatibility table](https://kotlinlang.org/docs/gradle-configure-project.html).
