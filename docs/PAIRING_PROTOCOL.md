# PocketCloud Pairing Protocol v1 (Bootstrap Only)

This document defines Stage 2's first phone-to-laptop trust bootstrap. It is not a job-dispatch or remote-shell protocol. The host is a Windows laptop process; the client is the native Android supervisor.

## Invitation

The laptop creates a fresh pairing ID, 256-bit one-time token, 256-bit random nonce, and expiry five minutes in the future. It generates a `pocketcloud://pair?...` QR URI with URL-encoded query fields:

- `v=1`
- `host`: numeric RFC1918 IPv4 or IPv6 ULA/LAN address, never a DNS name or public address
- `port`: TLS listener port
- `laptop_id`: fresh UUID for this host process; the current prototype deliberately does not persist the laptop private key or laptop ID
- `laptop_name`: display name
- `pairing_id`: fresh UUID
- `expires_at`: Unix seconds
- `nonce`: base64url without padding, 32 random bytes
- `token`: base64url without padding, 32 random bytes
- `spki_sha256`: base64url without padding, SHA-256 of the laptop TLS certificate's DER SubjectPublicKeyInfo

The host stores only a hash of the one-time token and the expected challenge in memory. It accepts a pairing request once, before expiry. The token is not a permanent identity credential. Since the laptop identity is ephemeral in this prototype, exit/restart creates a new laptop ID and TLS pin; the phone must pair again, and the session-scoped public-key record is not reused.

## TLS and local-only policy

The Android client connects to `https://{host}:{port}/v1/pair`. The server certificate contains the advertised numeric host in Subject Alternative Name. The Android client uses a trust manager that accepts only the certificate whose SubjectPublicKeyInfo hash equals `spki_sha256`; standard hostname verification remains enabled. Redirects are disabled. The client connect timeout is five seconds and its response timeout is four minutes to allow for explicit laptop approval; the server's socket read timeout is five seconds and it limits handler concurrency to eight. Requests and responses are limited to 8 KiB. The laptop binds only to the exact advertised private interface; wildcard listeners are refused. Public, DNS, multicast, and loopback invitation hosts are rejected by the Android parser. There is no relay or port-forwarding path.

TLS protects the payload in transit. The Android app does not send a generic command, file path, handler name, or job request during pairing.

## Client identity and proof

The phone creates a P-256 ECDSA signing key in Android Keystore. The private key is non-exportable; the public key is sent as X.509 SubjectPublicKeyInfo DER, base64url without padding. `phone_id` is the lowercase hex SHA-256 of those DER bytes. The user reviews the laptop name, local address, and key fingerprint, then explicitly approves on the phone.

The Android app signs UTF-8 bytes of exactly these newline-separated values, followed by one final newline:

```
pocketcloud-pair-v1
{pairing_id}
{laptop_id}
{phone_id}
{phone_name}
{lowercase_hex_sha256_of_public_key_der}
{nonce}
{expires_at}
```

Signature algorithm: ECDSA over P-256 with SHA-256. The DER-encoded ECDSA signature is base64url without padding.

## Pair request

`POST /v1/pair`, `Content-Type: application/json`, with exactly these fields:

```json
{
  "pairing_id": "<uuid>",
  "token": "<base64url>",
  "phone_id": "<64 lowercase hex chars>",
  "phone_name": "<1..64 printable characters>",
  "public_key_der": "<base64url>",
  "signature": "<base64url DER ECDSA signature>"
}
```

The host verifies field bounds, pairing ID, one-use token hash, expiry, P-256 curve, computed phone ID, challenge transcript signature, and that the phone is not already registered. It then displays the phone label and key fingerprint to the laptop operator and requires affirmative local approval; any other input denies. Only after approval does it persist the phone public key. The token is consumed on both approval and denial. Responses are bounded JSON and never include the token or private key.

Success response:

```json
{"paired":true,"laptop_id":"<uuid>","phone_id":"<64 lowercase hex chars>","phone_key_sha256":"<64 lowercase hex chars>"}
```

Errors use a generic `{"error":"pairing_rejected"}` shape to avoid leaking token-verification details. The client stores only the public laptop pin and IDs in app-private preferences; the phone private key remains in Android Keystore.

## Local pairing audit history

The laptop writes `pairing-audit.jsonl` beside its pairing records for cryptographically verified operator decisions only: `approval_granted` or `approval_denied`. Each line contains a UTC timestamp, pairing ID, verified phone ID, and phone-key SHA-256 fingerprint. It does not contain the QR token, signature, public-key bytes, phone display name, source address, or raw request. The file is append-only, capped at 1 MiB, and uses mode `0600` on POSIX; on Windows it inherits the containing directory's user ACL. HTTP access logging remains disabled. A grant is audited before the public-key record is persisted, so audit-write failure prevents that key from being stored. Malformed or unauthenticated requests are intentionally not logged to avoid credential exposure and unauthenticated log-filling.

## Threat boundaries and future work

This provides a same-LAN bootstrap with server-key pinning, phone proof-of-possession, short-lived replay protection, and explicit consent on both endpoints. Persistent laptop identity/key protection, phone backup/restore behavior, clock skew, LAN address transitions, revocation UI, secure persistent authenticated sessions, worker capability registration, and pairing soak/fuzz/device testing remain open gates. No remote execution or distributed job dispatch is exposed by this protocol.
