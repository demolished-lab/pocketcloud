"""Run the laptop-side same-LAN pairing bootstrap."""

from __future__ import annotations

import argparse
import base64
import ipaddress
import platform
import socket
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import qrcode

from .protocol import create_invitation, generate_ephemeral_tls_identity, validate_advertise, validate_listen
from .server import BoundedThreadingHTTPServer, PairingService, PairingStore, build_tls_context, make_handler


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pairing_host",
        description="Create one short-lived, local-only PocketCloud phone pairing invitation.",
    )
    parser.add_argument(
        "--advertise",
        required=True,
        help="numeric RFC1918 IPv4 or IPv6 ULA address to place in the invitation",
    )
    parser.add_argument("--port", type=int, required=True, help="explicit TLS listener port")
    parser.add_argument(
        "--listen",
        help="numeric bind address; if supplied it must exactly equal --advertise (wildcards are refused)",
    )
    parser.add_argument("--laptop-name", default=platform.node() or "PocketCloud laptop")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / ".pocketcloud" / "pairing",
        help="directory for private-permission public-key records",
    )
    return parser


def _console_approval(phone_name: str, phone_id: str, key_sha256: str) -> bool:
    print("\nPairing request received:")
    print(f"  Phone name: {phone_name}")
    print(f"  Phone ID: {phone_id}")
    print(f"  Phone public-key SHA-256: {key_sha256}")
    try:
        return input("Approve this phone on the laptop? Type YES to approve: ") == "YES"
    except (EOFError, KeyboardInterrupt):
        return False


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        advertised = validate_advertise(args.advertise)
        listen = validate_listen(args.listen or str(advertised), advertised)
        if not (1 <= args.port <= 65535):
            raise ValueError("--port must be between 1 and 65535")
        if not (1 <= len(args.laptop_name) <= 64) or not all(c.isprintable() for c in args.laptop_name):
            raise ValueError("--laptop-name must be 1..64 printable characters")
    except ValueError as exc:
        _parser().error(str(exc))

    laptop_id = str(uuid.uuid4())
    tls_key, certificate = generate_ephemeral_tls_identity(str(advertised))
    invitation, invitation_uri = create_invitation(
        host=str(advertised),
        port=args.port,
        laptop_id=laptop_id,
        laptop_name=args.laptop_name,
        public_key=tls_key.public_key(),
    )
    store = PairingStore(args.data_dir / f"paired-{laptop_id}.json")
    service = PairingService(invitation, store, _console_approval)

    if advertised.version == 6:
        class IPv6PairingHTTPServer(BoundedThreadingHTTPServer):
            address_family = socket.AF_INET6

        server_class = IPv6PairingHTTPServer
    else:
        server_class = BoundedThreadingHTTPServer

    try:
        httpd = server_class((listen, args.port), make_handler(service))
    except OSError as exc:
        print(f"Unable to listen on {listen}:{args.port}: {exc}", file=sys.stderr)
        return 2

    try:
        httpd.set_tls_context(build_tls_context(certificate, tls_key))
        endpoint_host = f"[{advertised}]" if advertised.version == 6 else str(advertised)
        expires_local = datetime.fromtimestamp(invitation.expires_at, timezone.utc).astimezone().isoformat(timespec="seconds")
        print("PocketCloud pairing host (bootstrap only; no remote command/job API)")
        print(f"Pair endpoint: https://{endpoint_host}:{args.port}/v1/pair")
        print(f"Listening on: {listen}:{args.port}")
        print(f"Invitation expires: {expires_local} (Unix {invitation.expires_at})")
        print(f"TLS certificate SPKI SHA-256 pin: {invitation.spki_sha256}")
        pin_bytes = base64.urlsafe_b64decode(invitation.spki_sha256 + "=")
        print("TLS certificate SPKI SHA-256 (compare with phone): " + ":".join(f"{byte:02X}" for byte in pin_bytes))
        print("Scan this QR on the phone while both devices are on the same trusted LAN:")
        qr = qrcode.QRCode(border=1)
        qr.add_data(invitation_uri)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
        # Drop the token-bearing invitation once its terminal QR has been rendered.
        del qr, invitation_uri
        print("No relay or port forwarding is enabled. This laptop identity is ephemeral;")
        print("after this host process exits, create a new invitation and pair again.")

        expiry_timer = threading.Timer(max(0, invitation.expires_at - time.time()), httpd.shutdown)
        expiry_timer.daemon = True
        expiry_timer.start()
        try:
            httpd.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            pass
        finally:
            expiry_timer.cancel()
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
