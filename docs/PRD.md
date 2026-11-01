# Product Requirements Document

## Product intent

PocketCloud turns an existing unrooted Android phone into the primary local control node for trusted personal workloads and paired consumer devices. Its first external worker is a Windows 11 laptop. The product favors resilience, local-first operation, user control, and verified behavior over feature count.

## Users and primary outcomes

The primary user owns the Android phone and Windows laptop and wants a transparent way to submit approved work, see device/job health, and recover safely after process or network interruption. The phone is the logical authority for registration, trust, and job assignment. A worker may complete an already-authorized leased job while the phone is unavailable, but may not assign itself new phone-owned work.

## MVP capabilities

The MVP ultimately includes a rootless Termux-based Android runtime; a narrow optional Kotlin lifecycle supervisor; persistent job state; approved Python handlers; a Windows Python worker with runtime capability discovery; device identity and explicit secure pairing; LAN-first authenticated encrypted sessions; leases, idempotency, offline result buffering, retries and reconciliation; resource-aware yielding; local SQLite and artifact storage; diagnostics, backups and restore; and a functional dashboard whose controls call real APIs.

## User priorities and product limitations

The phone remains a daily-use device. OS stability, calls and communication, interactive apps, essential PocketCloud functions, and optional computation have descending priority. Android may defer or terminate background work. Force-stop requires user relaunch; reboot recovery is best-effort; uptime and exact scheduled execution are not guaranteed. The system must tell the user when signals are unavailable and why work was paused.

PocketCloud is LAN-first. Optional VPN/relay adapters may be considered later; there is no mandatory external cloud, paid API, hosted relay, subscription, advertising, Gmail OAuth or public administrator endpoint. Remote reachability is not universal. The app does not provide true VMs or strong isolation from ordinary Termux processes. Registered trusted handlers are allowed; arbitrary remote code execution is not.

## Out of scope for the MVP

True virtual machines, Kubernetes, arbitrary public code execution, mandatory cloud/relay, unrestricted autonomous agents, advanced cron semantics, leader election, and public admin access are out of scope. Advanced scheduling, reverse proxy, storage abstractions, multi-worker scale, and hosted services are later work.

## Success definition

The MVP is complete only after the real phone and laptop pass the end-to-end scenario in the engineering brief: secure QR pairing; authenticated LAN session; phone-submitted registered task; result persisted on the laptop before acknowledgement and persisted on the phone on return; offline job queue and reconnect reconciliation; valid leased work finishing during a phone outage; and no silent task loss or duplicate effect for an idempotent handler. The proposed timing and stability objectives remain targets to measure, not guarantees.