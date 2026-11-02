# PocketCloud Android Supervisor

Native Java Android app for explicitly controlling the local PocketCloud runtime in Termux and bootstrapping phone-to-laptop trust using `docs/PAIRING_PROTOCOL.md`. The app does not start at boot, accept remote commands, or provide job dispatch.

## Build

Requirements: Android SDK Platform 36, JDK 17, and network access for Gradle/Maven dependencies. This module targets/compiles against SDK 36, supports API 24+, uses Java 17 and AGP 8.13.0, and uses ZXing Android Embedded 4.3.0 (Apache-2.0).

From this directory:

```sh
./gradlew testDebugUnitTest
./gradlew assembleDebug
```

The reproducible wrapper (Gradle 8.13) is included. The wrapper bootstrap was verified with `./gradlew --version`. **Build/test status for this sandbox: `./gradlew testDebugUnitTest` was attempted but failed during task configuration because no Android SDK (`ANDROID_HOME`/`sdk.dir`) is installed; no tests or Android compilation ran.** Eight Java/JUnit tests are present for invite parsing, address policy, tampering/expiry, canonical base64url, display-name policy and transcript bytes, but remain unexecuted. No Android device, emulator, Termux installation, or hardware behavior has been tested.

## Termux opt-in and controls

Install the repository/runtime in Termux and make the fixed script available at:

```text
/data/data/com.termux/files/home/pocketcloud/scripts/termux/supervisor.sh
```

The app invokes only `/data/data/com.termux/files/usr/bin/bash` with separate arguments `[fixed script path, start|stop|status]`, work directory `/data/data/com.termux/files/home`, and the documented `com.termux.RUN_COMMAND` / `com.termux.app.RunCommandService` boundary. Termux completion is returned through its one-shot pending-intent callback; the app validates the exit result and only removes the ongoing notification after confirmed Stop success. A missing callback leaves the notification visible with an unconfirmed-outcome message. The fixed script path is checked to remain under Termux home. No QR, network, or user-supplied command is passed to Termux.

Before use, install Termux 0.109 or later for result callbacks. Add `allow-external-apps=true` to `~/.termux/termux.properties` and run `termux-reload-settings`. Then manually grant PocketCloud `com.termux.permission.RUN_COMMAND` in Android Settings: **Apps → PocketCloud → Permissions → Additional permissions → Run commands in Termux environment**. The app opens PocketCloud's settings page if the permission is missing; this is a manual grant, not an in-app runtime permission prompt. Termux package/signature/version distributions differ; if Android cannot find the service, the app shows setup guidance. Keep the script executable and follow the shared repository's Termux setup steps for runtime dependencies.

Start is available only from the visible activity. On Android 13+, notification permission is requested with an explanation; Start is blocked if denied because the app cannot promise visible ongoing status. The foreground notification includes Stop and remains visible until Termux confirms the command result; no result within 30 seconds is not treated as success. There is no boot receiver or automatic start.

## Pairing behavior and storage

The scanner accepts only the v1 `pocketcloud://pair` invitation shape, private numeric RFC1918 IPv4 or IPv6 ULA addresses, bounded ports, canonical UUIDs, 32-byte base64url nonce/token/SPKI pin, and a fresh bounded expiry. It shows laptop name, numeric address, and SPKI SHA-256 before requiring explicit user approval. Only after approval does the app make an HTTPS POST to `/v1/pair` with a five-second connect timeout and a four-minute response timeout so the laptop operator can approve or deny locally; it pins exact certificate SPKI, leaves default hostname verification enabled for the advertised numeric SAN, disables redirects, and bounds request/response bodies to 8 KiB. Phone identity is a non-exportable P-256 Android Keystore key. App-private preferences keep only peer IDs and the public laptop SPKI pin; private key material is never stored in preferences or sent. Pairing does not create a remote command channel.

## Current limitations and review status

The Android 14+ service declares `specialUse` with a subtype for user-started local Termux supervision and shows an ongoing notification. **Google Play review/eligibility of this `specialUse` use case remains unresolved**; this implementation is not a claim of Play approval. The user must review the Termux distribution and grant permissions. Device lifecycle, OEM battery behavior, notification-denial paths, QR camera operation, TLS certificate SAN behavior on-device, LAN reachability, actual Termux bridge execution, pairing against the Windows host, backup/restore, and soak testing remain unverified. Pairing persistence/revocation UI and authenticated post-pairing sessions are not implemented.
