# Risk Register

| Risk | Severity | Mitigation / evidence needed | Status |
|---|---|---|---|
| Android background process death, Doze, OEM restrictions | Critical | Native supervisor where justified; durable state; restricted/intermittent mode; real lifecycle matrix and device profile | Open: target phone unknown |
| Foreground-service type/policy mismatch | Critical | Select only a purpose-matched type; verify current OS, target SDK and distribution policy before service implementation | Open |
| Termux bridge unavailable or user opt-in refused | High | Validate exact Termux build and RUN_COMMAND permissions; narrow interface; preserve queued work and provide manual launch | Open: no device |
| Phone resource/thermal impact | High | Native signal provenance, configurable thresholds, admission control, pause/resume hysteresis, real-device tests | Open |
| Laptop sleeping/offline/GPU driver mismatch | Medium | Runtime discovery and availability states; CPU fallback only if approved; no hidden sleep prevention | Open: Windows not attached |
| Secure pairing/replay/key compromise | Critical | Standard cryptography, one-use challenges, explicit fingerprint approval, revocation/key rotation and replay tests | Planned |
| Duplicate execution or stale lease | Critical | Idempotency/dedupe, lease epochs/fencing, bounded retry and needs_reconciliation on ambiguity | Planned |
| Arbitrary code execution | Critical | Approved handler registry only; no generic shell or arbitrary code endpoint | Design constraint |
| LAN-only remote reachability limits | High | Direct LAN first, optional VPN/relay adapter, offline buffer; honest UX about CGNAT/router limitations | Accepted limitation |
| SQLite corruption/busy/storage exhaustion | High | Single-writer per-device DB, transactions, migrations, database-size cap, reserved free space; add backup and demonstrated restore | Partial: Stage 1 admission/locking tested; backup/restore open |
| Dependency drift/supply-chain issue | High | Exact version pins, license review and lock; add hashes, update/rollback procedure and platform-specific install tests | Partial: Linux lock completed; hashes, rollback and Android build open |
| Scope creep into advanced agents/cloud | High | Stage gates and MVP exclusions; no broad build before Stage 1 plan approval | Controlled |

Severity and mitigations are initial engineering judgments from the supplied brief, not measured incident probabilities. Reassess after device audits and threat testing.
