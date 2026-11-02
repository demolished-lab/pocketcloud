# PocketCloud laptop pairing host (bootstrap only)

This package implements the laptop side of the v1 phone-to-laptop trust bootstrap in `../docs/PAIRING_PROTOCOL.md`. It is a small Python standard-library HTTPS server with P-256/X.509 and signature operations from `cryptography`, and terminal QR rendering through `qrcode`.

## Run

Use Python 3.11 or later. Install the pinned dependencies from the repository root, then start the host with the laptop's actual numeric LAN address:

```sh
python -m pip install -r requirements-pairing.lock
python -m pairing_host --advertise 192.168.1.20 --port 8765
```

`--advertise` is mandatory and accepts only RFC1918 IPv4 or IPv6 ULA addresses; DNS names, public addresses, loopback, multicast, and link-local addresses are rejected. The listener binds only to that exact advertised interface. If `--listen` is supplied, it must equal `--advertise`; wildcard binds such as `0.0.0.0` or `::` are refused so the endpoint is not accidentally exposed on another interface. Select a port allowed by the laptop firewall. The program does not configure firewall rules, port forwarding, or a relay.

The QR contains one five-minute invitation. The console shows the HTTPS endpoint, expiry, and TLS certificate SPKI SHA-256 pin in both base64url and colon-separated hexadecimal; the Android confirmation displays the same colon-separated form for manual comparison. The operator must type exactly `YES` locally to approve a verified phone; any other input denies and consumes the invitation. Pair records contain only the phone ID and public-key DER, are written atomically, and use user-private POSIX permissions (Windows ACLs are inherited from the user's data directory). The default record directory is `~/.pocketcloud/pairing`.

Verified operator grant/denial decisions are appended to `pairing-audit.jsonl` in that directory. The 1 MiB-capped JSONL records contain only a UTC timestamp, pairing ID, verified phone ID, event type and key fingerprint; they exclude tokens, signatures, public-key bytes, phone labels and source addresses. POSIX permissions are `0600`; Windows inherits the directory ACL. Audit-write failure fails closed before trust-key persistence.

## Identity and boundaries

The initial implementation deliberately keeps the laptop's P-256 TLS identity and laptop UUID ephemeral and does not persist a private key. The certificate key is written only to short-lived, private temporary files so Python's standard TLS server can load it, then those files are removed. This is not persistent encrypted key storage. Start a new host process and pair again after exit/restart; the QR pin and laptop ID will change. Public pairing records are session-scoped and are not reused by the next ephemeral laptop ID.

Only `POST /v1/pair` is implemented. Requests are capped at 8 KiB, socket reads time out after five seconds, and the server caps concurrent handler threads at eight. Bodies must match the exact schema and signed transcript in the protocol. Responses expose only the specified success fields or generic rejection shape. HTTP request/access logging is disabled to avoid credential disclosure; the separate audit log records only verified operator decisions. There is no remote shell, command, file-transfer, job, relay, or port-forwarding API.

## Tests and validation status

Run the focused Linux/sandbox tests with:

```sh
python -m unittest discover -s pairing_host/tests -v
```

The **17 Linux/sandbox unit tests** exercise protocol validation, signature verification, concurrent one-use handling, denial, bounded/private sanitized audit logging, storage idempotence/corruption handling, exact-interface binding, and the generic rejection boundary. The earlier 16-test baseline passed hosted Windows CI; the current audit addition awaits the next hosted run. These tests are not Windows laptop validation, end-to-end phone testing, or a security assessment. No Android device or Windows laptop result is claimed by this implementation.
