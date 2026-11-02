# Risk Register

| Risk | Severity | Mitigation / evidence needed | Status |
|---|---|---|---|
| Android background process death, Doze, OEM restrictions | Critical | User-visible foreground service; durable local state; restricted/intermittent mode; real lifecycle matrix and device profile | Open: target phone unknown; no uptime guarantee |
| Foreground-service type/policy mismatch | Critical | Use a purpose-appropriate type, document `specialUse` subtype, verify OS/target SDK and distribution policy | Android source compiles in hosted CI; Play review and target-device gate remain open |
| Termux bridge unavailable or user opt-in refused | High | Exact Termux version and RUN_COMMAND permission/allow-external-apps test; fixed allowlist; preserve manual launch | Linux shim tests cover fixed verbs, reject symlink/traversal state paths before mutation, and return nonzero without signalling an unrelated live PID; callback protocol documented; no Termux device test |
| Phone resource/thermal impact | High | Native signal provenance, configurable thresholds, admission control, pause/resume hysteresis, real-device tests | Open: resource manager is not implemented |
| Laptop sleeping/offline/GPU driver mismatch | Medium | Runtime discovery and availability states; CPU fallback only if approved; no hidden sleep prevention | Open: Windows laptop not attached |
| Secure pairing/replay/key compromise | Critical | One-use QR, TLS pin, phone signature, dual approval, replay/invalid-signature tests, bounded sanitized audit, revocation and rotation | Current 17 pairing-host tests pass on Linux and hosted Windows in CI run 41487865402, including approval audit log privacy/size controls. Physical phone/laptop pairing, independent security review, revocation and rotation remain open |
| Duplicate execution or stale lease | Critical | Idempotency/dedupe, lease epochs/fencing, bounded retry and `needs_reconciliation` on ambiguity | Stage 1 idempotency concurrency tested; distributed lease protocol remains future work |
| Arbitrary code execution | Critical | Approved handler registry only; no generic shell or arbitrary code endpoint | Design constraint and current allowlist implemented; pairing carries no commands |
| LAN-only remote reachability limits | High | Direct LAN first, optional VPN adapter, offline buffer; show unavailable path honestly | Pairing requires numeric private/ULA address; no relay/port forwarding |
| SQLite corruption/busy/storage exhaustion | High | Single-writer DB, checksummed migrations, integrity checks, admission, backup/restore and power-loss tests | Host corruption injection/header preservation and limits tested; backup/restore and target filesystem remain open |
| Dependency drift/supply-chain issue | High | Exact pins, license review, hashes, rollback and advisory review | 8-package lock resolved; Android arm64 binary-only wheel probe passes; actual Termux install, hashes/rollback still open |
| Short host tests mistaken for reliability | High | Bounded soak tool, 1/6/12/24-hour runs, target-device power/network/failure matrix | 15-minute Linux host soak passed with 180 checks and zero failures; longer soaks and target-device tests remain open |
| Scope creep into advanced agents/cloud | High | Stage gates and MVP exclusions; no broad build before review | Controlled by stage records |
| Public code reuse/license ambiguity | Medium | Select clear repository license and preserve third-party notices | MIT license and initial dependency inventory added; complete resolved APK license report remains required before release |

Severity and mitigations are initial engineering judgments from the supplied brief, not measured incident probabilities. Reassess after device audits, protocol review and independent security testing.
