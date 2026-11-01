# PocketCloud

PocketCloud is a local-first personal infrastructure platform. Its intended controller is an unrooted Android phone; the first external worker is a Windows 11 laptop. The product is designed around durable state, explicit trust, approved handlers, and transparent resource protection—not virtual machines or guaranteed uptime.

## Current status

This repository currently contains the Stage 0 feasibility and planning package only. No Android app, worker, runtime service, pairing protocol, or dashboard has been implemented. The supplied engineering brief requires a review gate before Stage 1 implementation, so development is paused pending confirmation of the target Android device and approval of the Stage 1 plan.

The current Manus execution environment is a Linux x86_64 sandbox. It has Python 3.12.3, Node.js 22.23.4, and GitHub CLI, but no ADB, Android SDK manager, Gradle, connected Android device, or Windows host. These are environment observations, not facts about the user's devices.

## Documents

- [Stage 0 feasibility report](docs/STAGE_0_FEASIBILITY.md)
- [Stage 1 implementation plan](docs/STAGE_1_PLAN.md)
- [Product requirements](docs/PRD.md)
- [Software requirements](docs/SRS.md)
- [Technical requirements and dependency proposal](docs/TRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security and threat model](docs/SECURITY_AND_THREAT_MODEL.md)
- [Risk register](docs/RISK_REGISTER.md)
- [Staged validation plan](docs/STAGED_TEST_PLAN.md)
- [Decision log](docs/DECISIONS.md)

## Non-negotiable boundaries

- No root, bootloader unlock, ROM/system modification, exploits, or hidden persistence.
- Do not describe PRoot or a managed process as a VM or security boundary.
- Workers execute registered, approved handlers only; there is no arbitrary remote shell endpoint.
- Persist authoritative state before acknowledging work. Use at-least-once delivery, idempotency, and reconciliation; never promise universal exactly-once execution.
- LAN-first operation must not depend on paid APIs, external cloud, Gmail OTP, or hosted relay.
- Android remains a daily-use device. User activity and OS stability outrank optional computation.
- Stage gates require evidence. Missing hardware or real-device tests remain explicitly incomplete.

## License

No repository license has been selected yet. Public visibility does not itself grant permission to reuse code. Add a license only after the maintainer selects one.