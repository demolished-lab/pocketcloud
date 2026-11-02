"""Protocol primitives for PocketCloud's local-only pairing bootstrap."""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

MAX_REQUEST_BYTES = 8192
PAIR_FIELDS = frozenset(
    {"pairing_id", "token", "phone_id", "phone_name", "public_key_der", "signature"}
)


class PairingRejected(Exception):
    """A request failed validation; callers must return only the generic error."""


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(value: Any, *, max_decoded: int) -> bytes:
    if not isinstance(value, str) or not value or "=" in value:
        raise PairingRejected
    try:
        raw_ascii = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise PairingRejected from exc
    if any(c not in b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in raw_ascii):
        raise PairingRejected
    if len(raw_ascii) > ((max_decoded * 4 + 2) // 3):
        raise PairingRejected
    try:
        decoded = base64.urlsafe_b64decode(raw_ascii + b"=" * ((-len(raw_ascii)) % 4))
    except (ValueError, base64.binascii.Error) as exc:
        raise PairingRejected from exc
    if not decoded or len(decoded) > max_decoded or b64url_encode(decoded) != value:
        raise PairingRejected
    return decoded


def validate_advertise(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Accept only RFC1918 IPv4 or IPv6 ULA addresses, never routable/public hosts."""
    if not isinstance(value, str) or not value or "%" in value:
        raise ValueError("--advertise must be a numeric RFC1918 IPv4 or IPv6 ULA address")
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("--advertise must be a numeric RFC1918 IPv4 or IPv6 ULA address") from exc
    allowed = False
    if isinstance(address, ipaddress.IPv4Address):
        allowed = any(
            address in ipaddress.ip_network(network)
            for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
        )
    else:
        allowed = address in ipaddress.ip_network("fc00::/7")
    if not allowed or address.is_loopback or address.is_multicast or address.is_unspecified:
        raise ValueError("--advertise must be a numeric RFC1918 IPv4 or IPv6 ULA address")
    return address


def validate_listen(value: str, advertise: ipaddress._BaseAddress) -> str:
    """Only bind the exact advertised private interface; wildcard exposure is refused."""
    if not isinstance(value, str) or "%" in value:
        raise ValueError("--listen must be a numeric address or same-family wildcard")
    try:
        listen = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("--listen must be a numeric address or same-family wildcard") from exc
    if listen.version != advertise.version:
        raise ValueError("--listen and --advertise must use the same IP family")
    if listen != advertise:
        raise ValueError("--listen must equal --advertise; wildcard binds are not allowed")
    return str(listen)


def phone_transcript(
    pairing_id: str,
    laptop_id: str,
    phone_id: str,
    phone_name: str,
    key_sha256: str,
    nonce: str,
    expires_at: int,
) -> bytes:
    values = (
        "pocketcloud-pair-v1",
        pairing_id,
        laptop_id,
        phone_id,
        phone_name,
        key_sha256,
        nonce,
        str(expires_at),
    )
    return ("\n".join(values) + "\n").encode("utf-8")


@dataclass(frozen=True)
class Invitation:
    pairing_id: str
    token_hash: bytes
    nonce: str
    expires_at: int
    laptop_id: str
    laptop_name: str
    host: str
    port: int
    spki_sha256: str


def create_invitation(
    *,
    host: str,
    port: int,
    laptop_id: str,
    laptop_name: str,
    public_key: ec.EllipticCurvePublicKey,
    now: int | None = None,
) -> tuple[Invitation, str]:
    address = validate_advertise(host)
    if not (1 <= port <= 65535):
        raise ValueError("port must be between 1 and 65535")
    if str(uuid.UUID(laptop_id)) != laptop_id:
        raise ValueError("laptop_id must be a canonical UUID")
    if not (1 <= len(laptop_name) <= 64) or not all(c.isprintable() for c in laptop_name):
        raise ValueError("laptop_name must be 1..64 printable characters")
    pairing_id = str(uuid.uuid4())
    expires_at = (int(datetime.now(timezone.utc).timestamp()) if now is None else now) + 300
    token_bytes = secrets.token_bytes(32)
    nonce = b64url_encode(secrets.token_bytes(32))
    token = b64url_encode(token_bytes)
    spki = public_key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    spki_sha256 = b64url_encode(hashlib.sha256(spki).digest())
    fields = {
        "v": "1",
        "host": str(address),
        "port": str(port),
        "laptop_id": laptop_id,
        "laptop_name": laptop_name,
        "pairing_id": pairing_id,
        "expires_at": str(expires_at),
        "nonce": nonce,
        "token": token,
        "spki_sha256": spki_sha256,
    }
    uri = "pocketcloud://pair?" + urlencode(fields)
    invitation = Invitation(
        pairing_id=pairing_id,
        token_hash=hashlib.sha256(token_bytes).digest(),
        nonce=nonce,
        expires_at=expires_at,
        laptop_id=laptop_id,
        laptop_name=laptop_name,
        host=str(address),
        port=port,
        spki_sha256=spki_sha256,
    )
    return invitation, uri


def generate_ephemeral_tls_identity(
    advertised_host: str,
) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    """Create a fresh P-256 TLS identity with the advertised IP in its SAN."""
    address = validate_advertise(advertised_host)
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PocketCloud Pairing")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(address)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    return key, certificate
