"""Minimal HTTPS pairing endpoint; deliberately exposes no command/job routes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import ssl
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .protocol import (
    MAX_REQUEST_BYTES,
    PAIR_FIELDS,
    Invitation,
    PairingRejected,
    b64url_decode,
    b64url_encode,
    phone_transcript,
)

ERROR_BODY = {"error": "pairing_rejected"}
PHONE_ID_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_AUDIT_LOG_BYTES = 1024 * 1024


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """Small worker pool and request queue for the short-lived local pairing endpoint."""

    daemon_threads = True
    request_queue_size = 16
    max_workers = 8

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._worker_slots = threading.BoundedSemaphore(self.max_workers)
        self._tls_context: ssl.SSLContext | None = None
        super().__init__(*args, **kwargs)

    def set_tls_context(self, context: ssl.SSLContext) -> None:
        self._tls_context = context

    def get_request(self) -> tuple[Any, Any]:
        request, client_address = super().get_request()
        request.settimeout(5.0)
        if self._tls_context is not None:
            try:
                request = self._tls_context.wrap_socket(
                    request, server_side=True, do_handshake_on_connect=False
                )
                request.settimeout(5.0)
            except Exception:
                request.close()
                raise
        return request, client_address

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self._worker_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._worker_slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._worker_slots.release()


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PairingRejected
        result[key] = value
    return result


class PairingStore:
    """Atomic, private-permission storage of approved phone public keys only."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.audit_path = self.path.parent / "pairing-audit.jsonl"
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            # Windows ACLs are inherited from the per-user directory; chmod is not portable there.
            pass
        self._lock = threading.Lock()

    def _read(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("pairing store is unreadable; refusing to overwrite it") from exc
        if not isinstance(value, list) or any(
            not isinstance(item, dict)
            or set(item) != {"phone_id", "public_key_der"}
            or not isinstance(item["phone_id"], str)
            or not isinstance(item["public_key_der"], str)
            for item in value
        ):
            raise RuntimeError("pairing store has an invalid format")
        return value

    def has_phone(self, phone_id: str) -> bool:
        with self._lock:
            return any(item["phone_id"] == phone_id for item in self._read())

    def add(self, phone_id: str, public_key_der: bytes) -> None:
        encoded = b64url_encode(public_key_der)
        with self._lock:
            records = self._read()
            if any(item["phone_id"] == phone_id for item in records):
                raise PairingRejected
            records.append({"phone_id": phone_id, "public_key_der": encoded})
            payload = (json.dumps(records, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
            temp_name: str | None = None
            try:
                fd, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent)
                try:
                    if hasattr(os, "fchmod"):
                        os.fchmod(fd, 0o600)
                    with os.fdopen(fd, "wb") as handle:
                        handle.write(payload)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temp_name, self.path)
                    temp_name = None
                    if os.name != "nt":
                        os.chmod(self.path, 0o600)
                        dir_fd = os.open(self.path.parent, os.O_RDONLY)
                        try:
                            os.fsync(dir_fd)
                        finally:
                            os.close(dir_fd)
                finally:
                    if temp_name is not None:
                        try:
                            os.unlink(temp_name)
                        except FileNotFoundError:
                            pass
            except OSError as exc:
                raise RuntimeError("could not persist pairing record") from exc

    def records(self) -> list[dict[str, str]]:
        with self._lock:
            return list(self._read())

    def record_audit_event(
        self,
        event: str,
        pairing_id: str,
        phone_id: str,
        phone_key_sha256: str,
    ) -> None:
        """Append a verified operator decision, excluding request secrets and personal labels."""
        if event not in {"approval_granted", "approval_denied"}:
            raise ValueError("unsupported pairing audit event")
        if not PHONE_ID_RE.fullmatch(phone_id) or not PHONE_ID_RE.fullmatch(phone_key_sha256):
            raise ValueError("invalid phone identity in pairing audit event")
        try:
            if str(uuid.UUID(pairing_id)) != pairing_id:
                raise ValueError("invalid pairing ID in audit event")
        except ValueError as exc:
            raise ValueError("invalid pairing ID in audit event") from exc

        event_record = {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "event": event,
            "pairing_id": pairing_id,
            "phone_id": phone_id,
            "phone_key_sha256": phone_key_sha256,
        }
        payload = (json.dumps(event_record, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
        with self._lock:
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                fd = os.open(self.audit_path, flags, 0o600)
            except OSError as exc:
                raise RuntimeError("could not open pairing audit log") from exc
            try:
                if os.name != "nt" and hasattr(os, "fchmod"):
                    os.fchmod(fd, 0o600)
                if os.fstat(fd).st_size + len(payload) > MAX_AUDIT_LOG_BYTES:
                    raise RuntimeError("pairing audit log size limit reached")
                written = os.write(fd, payload)
                if written != len(payload):
                    raise RuntimeError("incomplete pairing audit log write")
                os.fsync(fd)
            except OSError as exc:
                raise RuntimeError("could not persist pairing audit event") from exc
            finally:
                os.close(fd)


class PairingService:
    def __init__(
        self,
        invitation: Invitation,
        store: PairingStore,
        approve: Callable[[str, str, str], bool],
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.invitation = invitation
        self.store = store
        self.approve = approve
        self.clock = clock
        self._state_lock = threading.Lock()
        self._consumed = False

    @property
    def consumed(self) -> bool:
        with self._state_lock:
            return self._consumed

    def process_body(self, body: bytes) -> tuple[int, dict[str, Any]]:
        try:
            if not isinstance(body, bytes) or len(body) > MAX_REQUEST_BYTES:
                raise PairingRejected
            try:
                document = json.loads(body.decode("utf-8"), object_pairs_hook=_reject_duplicate_json_keys)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PairingRejected from exc
            if not isinstance(document, dict) or set(document) != PAIR_FIELDS:
                raise PairingRejected

            pairing_id = document["pairing_id"]
            if not isinstance(pairing_id, str) or pairing_id != self.invitation.pairing_id:
                raise PairingRejected
            try:
                if str(uuid.UUID(pairing_id)) != pairing_id:
                    raise PairingRejected
            except ValueError as exc:
                raise PairingRejected from exc

            token_bytes = b64url_decode(document["token"], max_decoded=32)
            if len(token_bytes) != 32 or not hmac.compare_digest(
                hashlib.sha256(token_bytes).digest(), self.invitation.token_hash
            ):
                raise PairingRejected

            phone_id = document["phone_id"]
            if not isinstance(phone_id, str) or not PHONE_ID_RE.fullmatch(phone_id):
                raise PairingRejected
            phone_name = document["phone_name"]
            if (
                not isinstance(phone_name, str)
                or not (1 <= len(phone_name) <= 64)
                or not all(character.isprintable() for character in phone_name)
            ):
                raise PairingRejected

            public_key_der = b64url_decode(document["public_key_der"], max_decoded=256)
            try:
                public_key = serialization.load_der_public_key(public_key_der)
            except (ValueError, TypeError) as exc:
                raise PairingRejected from exc
            if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(
                public_key.curve, ec.SECP256R1
            ):
                raise PairingRejected
            key_sha256 = hashlib.sha256(public_key_der).hexdigest()
            if not hmac.compare_digest(key_sha256, phone_id):
                raise PairingRejected

            signature = b64url_decode(document["signature"], max_decoded=128)
            transcript = phone_transcript(
                pairing_id,
                self.invitation.laptop_id,
                phone_id,
                phone_name,
                key_sha256,
                self.invitation.nonce,
                self.invitation.expires_at,
            )
            try:
                public_key.verify(signature, transcript, ec.ECDSA(hashes.SHA256()))
            except (InvalidSignature, ValueError) as exc:
                raise PairingRejected from exc

            with self._state_lock:
                if self._consumed or self.clock() >= self.invitation.expires_at:
                    raise PairingRejected
                if self.store.has_phone(phone_id):
                    raise PairingRejected
                # Consume before asking the laptop operator: denial and approval are both one-use.
                self._consumed = True

            approved = self.approve(phone_name, phone_id, key_sha256)
            if approved is not True:
                self.store.record_audit_event(
                    "approval_denied", pairing_id, phone_id, key_sha256
                )
                raise PairingRejected
            self.store.record_audit_event("approval_granted", pairing_id, phone_id, key_sha256)
            self.store.add(phone_id, public_key_der)
            return 200, {
                "paired": True,
                "laptop_id": self.invitation.laptop_id,
                "phone_id": phone_id,
                "phone_key_sha256": key_sha256,
            }
        except PairingRejected:
            return 400, dict(ERROR_BODY)
        except Exception:
            # Keep implementation, storage, and operator failures indistinguishable on the wire.
            return 400, dict(ERROR_BODY)


def build_tls_context(certificate: Any, private_key: ec.EllipticCurvePrivateKey):
    """Load an ephemeral cert/key through short-lived private temporary files."""
    import ssl

    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    temp_dir = tempfile.mkdtemp(prefix="pocketcloud-pairing-tls-")
    if os.name != "nt":
        os.chmod(temp_dir, 0o700)
    cert_path = os.path.join(temp_dir, "cert.pem")
    key_path = os.path.join(temp_dir, "key.pem")
    try:
        for path, content in ((cert_path, cert_pem), (key_path, key_pem)):
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            fd = os.open(path, flags, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        return context
    finally:
        for path in (cert_path, key_path):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass


def make_handler(service: PairingService):
    from http.server import BaseHTTPRequestHandler

    class PairingHandler(BaseHTTPRequestHandler):
        server_version = "PocketCloudPairing/1"
        sys_version = ""

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(5.0)
            if isinstance(self.connection, ssl.SSLSocket):
                self.connection.do_handshake()

        def log_message(self, format: str, *args: Any) -> None:
            # Access logs are intentionally disabled to avoid accidental credential logging.
            return

        def _send(self, status: int, body: dict[str, Any]) -> None:
            payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)
            self.close_connection = True

        def do_POST(self) -> None:
            if self.path != "/v1/pair":
                self._send(404, dict(ERROR_BODY))
                return
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json" or self.headers.get("Content-Encoding"):
                self._send(400, dict(ERROR_BODY))
                return
            if self.headers.get("Transfer-Encoding"):
                self._send(400, dict(ERROR_BODY))
                return
            length_header = self.headers.get("Content-Length")
            if length_header is None or not length_header.isascii() or not length_header.isdigit():
                self._send(400, dict(ERROR_BODY))
                return
            length = int(length_header)
            if length > MAX_REQUEST_BYTES:
                self._send(413, dict(ERROR_BODY))
                return
            try:
                body = self.rfile.read(length)
            except OSError:
                return
            if len(body) != length:
                self._send(400, dict(ERROR_BODY))
                return
            status, response = service.process_body(body)
            self._send(status, response)

        def _unsupported(self) -> None:
            self._send(404, dict(ERROR_BODY))

        do_GET = _unsupported
        do_HEAD = _unsupported
        do_PUT = _unsupported
        do_DELETE = _unsupported
        do_PATCH = _unsupported
        do_OPTIONS = _unsupported

    return PairingHandler
