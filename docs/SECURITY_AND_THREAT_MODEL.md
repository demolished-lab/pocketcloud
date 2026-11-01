# Security and Threat Model

## Assets and trust boundaries

Assets include device private keys/trust records, authorization and revocation state, job payloads/results, local databases/artifacts, configuration, and audit logs. Trust boundaries exist between phone and laptop; app and Termux; local UI and control API; discovery and authenticated transport; and worker process and host OS. Ordinary Termux processes share the phone's OS/user context. A per-job directory is not an enforceable sandbox.

## Threats and required controls

- **Unauthenticated remote execution:** expose no arbitrary command or shell endpoint. Accept only registered handler IDs/versions and bounded schemas.
- **Rogue/replayed pairing:** QR challenge is short-lived and single-use; show both identities/fingerprints; require explicit approval; perform challenge-response; establish authenticated encryption; persist trust; reject replay; permit revocation and key rotation.
- **Compromised or revoked peer:** apply role/capability authorization, session invalidation, lease epochs/fencing, and audit privileged actions. Pairing grants only declared capabilities.
- **Duplicate effects or stale authority:** idempotency keys, dedupe records, at-least-once delivery, lease expiry, fencing, durable state, and reconciliation quarantine.
- **Malicious/malformed payload:** strict handler allowlist, schema validation, payload/output limits, timeouts, path validation, restricted environment, and process-tree control where feasible.
- **Secret leakage:** protect private keys using native/OS facilities when available; never hard-code keys; redact credentials, tokens, auth headers, cookies, and recovery codes from logs/exports.
- **Network interception/discovery spoofing:** authenticated encrypted sessions and pinned device identity; mDNS/NSD does not create trust; no public admin port by default.
- **Database/storage failure:** transactions, integrity checks, quotas, reserved recovery space, backups and tested restore. Never silently delete active task state.
- **Resource abuse/user disruption:** conservative configurable admission; optional work yields under critical device conditions; no hidden wake lock or sleep prevention.

## Explicit limitations

The MVP does not claim VM isolation, root-level process containment, protection against a compromised OS, universal uptime, or universal remote reachability. Workloads are trusted approved handlers and may share the ordinary device account's privileges. End-to-end claims require independent security tests; documentation alone is not proof.

## Audit events

Record pairing approval, key changes, revocation, privileged action, dispatch/lease transitions, result receipt, resource policy change, and reconciliation decisions. Audit records are bounded and sanitized. Exports state signal provenance and omit secrets/personal data.