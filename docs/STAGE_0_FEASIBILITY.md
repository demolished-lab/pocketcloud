# Stage 0 — Feasibility and Environment Audit

**Status:** The sandbox environment and target uncertainties are documented. The target-device audit remains incomplete. The Stage 1 plan was approved by the user on 2026-11-02 and host implementation has since been completed; neither host evidence nor approval substitutes for target-device verification.

## What was actually inspected

The supplied brief identifies the intended laptop as Windows 11 with Ryzen 5 7535HS, 16 GB RAM, and an NVIDIA RTX 3050 Laptop GPU with 6 GB VRAM. These are user-provided target specifications, not measurements made by this session. The brief does not identify the Android make/model, Android version/API, memory, storage, battery capacity, chipset, or OEM restrictions.

The execution environment inspected for this task is Linux x86_64, Python 3.12.3, Node.js 22.23.4, and GitHub CLI. `adb` is unavailable; Java exists, but Gradle and `sdkmanager` are unavailable. There is no attached Android device, Windows host, or PowerShell bridge. Therefore no phone property, Windows driver/CUDA state, GPU compatibility, disk capacity, sleep behavior, or real-device lifecycle result can be verified here.

## Platform feasibility findings

Android foreground services are not a general uptime exemption. Apps targeting Android 14 or later must declare a service type that matches the actual use case, request the associated permissions, and satisfy runtime prerequisites; invalid or missing declarations can cause system exceptions [1]. PocketCloud must not misuse media playback. The exact service type, package-distribution policy, target SDK, and OS-specific restrictions must be validated against the chosen Android version before release.

Android recommends choosing the API that matches the work. WorkManager is appropriate for many deferrable jobs, while continuous user-noticeable work may require a foreground service; background-start restrictions still apply. WorkManager must not be represented as an exact-cron or permanent-service guarantee [2].

Termux documents a narrow `RUN_COMMAND` integration. The requesting Android app must declare and obtain `com.termux.permission.RUN_COMMAND`; the user must enable `allow-external-apps` in Termux settings, and Android package-visibility requirements also apply for newer target SDKs [3]. The bridge is viable only if it is explicitly opt-in, tested with the distributed Termux build/version, and limited to fixed PocketCloud entry points.

## Dependency decision

The initial Stage 1 proposal below was superseded after Android wheel-resolution checks. The implemented runtime uses Starlette 1.10.0, Uvicorn 0.54.0, and SQLAlchemy 2.1.6, with project-owned checksummed SQLite migrations. FastAPI/Pydantic Core and Alembic/Mako were removed from the runtime dependency path. The eight-package Android arm64 CPython 3.12 lock resolves to binary wheels in CI, but that result does not prove installation in the target Termux environment. Host state remains local-first and does not require remote services or API keys.

## Stage 0 exit evidence

- Environment inventory: completed for this sandbox, not target hardware.
- Android/Termux platform constraints: initial official-source review completed; target-version compatibility remains open.
- Threat and architecture boundaries: recorded in companion documents.
- Phone audit: blocked because no phone is attached and the identifying facts cannot be inferred.
- Windows worker audit: blocked because no Windows host is attached; the supplied hardware description is not runtime verification.
- Stage 1 plan: approved by the user on 2026-11-02; host implementation exists, while its target-device gate remains open.

## Information needed to complete the device-specific audit

Please provide the Android phone manufacturer/model and Android version (or API level), plus available RAM and free internal storage if visible in Settings. Also provide the Termux distribution/version and confirm whether the specified Windows 11 laptop is physically available for later worker tests. If device access is available through another authorized environment, it can be selected for a direct audit; otherwise these details must come from the user.

## References

[1]: https://developer.android.com/about/versions/14/changes/fgs-types-required "Foreground service types are required"
[2]: https://developer.android.com/develop/background-work/background-tasks "Background tasks overview"
[3]: https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent "Termux RUN_COMMAND Intent"
