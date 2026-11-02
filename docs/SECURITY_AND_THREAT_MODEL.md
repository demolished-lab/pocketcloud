# Security and Threat Model

## Assets and trust boundaries

Assets include device private keys/trust records, authorization and revocation state, job payloads/results, local databases/artifacts, configuration, and audit logs. Trust boundaries exist between phone and laptop; app and Termux; local UI and control API; discovery and authenticated transport; and worker process and host OS. Ordinary Termux processes share the phone's OS/user context. A per-job directory is not an enforceable sandbox.

## Threats and required controls

- **Unauthenticated remote execution:** expose no arbitrary command or shell endpoint. Accept only registered handler IDs/versions and bounded schemas. The Stage 2 Termux bridge allows only fixed local supervisor verbs.
- **Rogue/replayed pairing:** protocol v1 uses a five-minute, single-use token; phone Keystore P-256 signature over a laptop challenge; TLS SPKI pin from the QR; private/ULA numeric host; and explicit phone plus laptop approval. See `docs/PAIRING_PROTOCOL.md`. Pairing writes a public phone key only and grants no command/job capability.
- **Compromised or revoked peer:** later sessions must enforce roles/capabilities, session invalidation, lease epochs/fencing, and audit privileged actions. Pair-host revocation, key rotation, authenticated session persistence and recovery are not yet proven.
- **Duplicate effects or stale authority:** idempotency keys, dedupe records, at-least-once delivery, lease expiry, fencing, durable state, and reconciliation quarantine. Stage 1 covers local idempotency; distributed leases remain future work.
- **Malicious/malformed payload:** strict handler allowlist, schema validation, body/output limits, timeouts, path validation, restricted environment, and process-tree control where feasible. QR input is bounded and never interpreted as a shell command. The Termux control script rejects `..` and symlinked state-path components before directory chmod/creation; Linux regression tests cover final and parent symlinks.
- **Secret leakage:** protect phone private key in Android Keystore; never hard-code keys; redact credentials, tokens, auth headers, cookies, signatures and recovery codes from logs/exports. The laptop key-at-rest and peer-store protections require code review and target Windows validation.
- **Network interception/discovery spoofing or resource exhaustion:** authenticated encrypted sessions and pinned device identity; mDNS/NSD does not create trust; no public admin port by default. Pairing binds only the advertised private interface, caps request workers, and performs TLS handshakes inside those workers with a deadline; a slow-client regression proves another worker can still process a request. Pairing has no relay or port-forwarding path. These controls do not substitute for fuzzing or independent security review.
- **Database/storage failure:** Stage 1 has transactions, checksummed SQL migrations, a single-process lock, private-home/mode checks, `quick_check`, a DB cap and reserved-free-space admission. Host fault injection detects corrupt headers and a damaged SQLite page; free-space remains point-in-time. Backup/restore, power-loss behavior and filesystem-specific recovery remain open.
- **Resource abuse/user disruption:** conservative configurable admission; optional work yields under critical device conditions; no hidden wake lock, boot persistence, or sleep prevention. No target-device thermal/Doze evidence exists.

## Explicit limitations

The MVP does not claim VM isolation, root-level process containment, protection against a compromised OS, universal uptime, Play policy approval, or universal remote reachability. The current pairing protocol is a bootstrap only, not a complete authenticated session or job-dispatch protocol. Workloads are trusted approved handlers and may share the ordinary device account's privileges. End-to-end claims require target-hardware tests and independent security assessment; documentation alone is not proof.

## Audit events

The pairing host currently records cryptographically verified operator approval grants and denials in a sanitized, append-only JSONL file capped at 1 MiB. Each record includes a timestamp, pairing ID, verified phone ID and key fingerprint; it omits tokens, signatures, public-key bytes, phone labels and source addresses. Malformed or unauthenticated requests are not recorded. HTTP access logging remains disabled. The 1 MiB cap, private POSIX mode, Windows inherited ACL and fail-closed grant path have host tests.

The broader audit requirement remains open: key changes, revocation, privileged actions, dispatch/lease transitions, result receipt, resource policy changes and reconciliation decisions do not yet exist or have audit events. Future audit records must remain bounded and sanitized; exports must state signal provenance and omit secrets/personal data.
