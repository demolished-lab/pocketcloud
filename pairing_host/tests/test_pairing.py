from __future__ import annotations

import hashlib
import json
import socket
import ssl
import threading
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from pairing_host.protocol import (
    MAX_REQUEST_BYTES,
    PairingRejected,
    b64url_encode,
    create_invitation,
    generate_ephemeral_tls_identity,
    phone_transcript,
    validate_advertise,
    validate_listen,
)
from pairing_host.server import (
    BoundedThreadingHTTPServer,
    PairingService,
    PairingStore,
    ERROR_BODY,
    build_tls_context,
    make_handler,
)


class PairingHostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp.name) / "paired.json"
        self.store = PairingStore(self.store_path)
        self.tls_key, self.certificate = generate_ephemeral_tls_identity("192.168.1.20")
        self.laptop_id = str(uuid.uuid4())
        self.invitation, self.invitation_uri = create_invitation(
            host="192.168.1.20",
            port=8765,
            laptop_id=self.laptop_id,
            laptop_name="Test laptop",
            public_key=self.tls_key.public_key(),
            now=1000,
        )
        self.token = dict(parse_qsl(urlsplit(self.invitation_uri).query))["token"]
        self.approvals: list[tuple[str, str, str]] = []
        self.service = self._service(approve=True)
        self.phone_key = ec.generate_private_key(ec.SECP256R1())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _service(self, *, approve: bool, invitation=None, store=None, now=1100):
        return PairingService(
            invitation or self.invitation,
            store or self.store,
            lambda name, phone_id, fingerprint: self._approve(approve, name, phone_id, fingerprint),
            clock=lambda: now,
        )

    def _approve(self, approve: bool, name: str, phone_id: str, fingerprint: str) -> bool:
        self.approvals.append((name, phone_id, fingerprint))
        return approve

    def _request(self, *, key=None, signature_from=None, phone_name="My phone", der=None, pairing_id=None, invitation=None):
        key = key or self.phone_key
        invitation = invitation or self.invitation
        if der is None:
            der = key.public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        phone_id = hashlib.sha256(der).hexdigest()
        key_hash = hashlib.sha256(der).hexdigest()
        signed_by = signature_from or key
        transcript = phone_transcript(
            pairing_id or invitation.pairing_id,
            invitation.laptop_id,
            phone_id,
            phone_name,
            key_hash,
            invitation.nonce,
            invitation.expires_at,
        )
        signature = signed_by.sign(transcript, ec.ECDSA(hashes.SHA256()))
        return {
            "pairing_id": pairing_id or invitation.pairing_id,
            "token": self.token,
            "phone_id": phone_id,
            "phone_name": phone_name,
            "public_key_der": b64url_encode(der),
            "signature": b64url_encode(signature),
        }

    @staticmethod
    def _body(request: dict) -> bytes:
        return json.dumps(request, separators=(",", ":")).encode("utf-8")

    def test_valid_pairing_persists_only_public_key_and_exact_success_body(self) -> None:
        request = self._request()
        status, response = self.service.process_body(self._body(request))
        self.assertEqual(status, 200)
        self.assertEqual(set(response), {"paired", "laptop_id", "phone_id", "phone_key_sha256"})
        self.assertEqual(response["paired"], True)
        self.assertEqual(response["laptop_id"], self.laptop_id)
        self.assertEqual(response["phone_id"], request["phone_id"])
        self.assertEqual(response["phone_key_sha256"], request["phone_id"])
        records = self.store.records()
        self.assertEqual(len(records), 1)
        self.assertEqual(set(records[0]), {"phone_id", "public_key_der"})
        self.assertNotIn(self.token, self.store_path.read_text(encoding="utf-8"))
        audit_path = self.store_path.parent / "pairing-audit.jsonl"
        audit_text = audit_path.read_text(encoding="utf-8")
        audit_event = json.loads(audit_text)
        self.assertEqual(audit_event["event"], "approval_granted")
        self.assertEqual(audit_event["pairing_id"], self.invitation.pairing_id)
        self.assertEqual(audit_event["phone_id"], request["phone_id"])
        self.assertEqual(audit_event["phone_key_sha256"], request["phone_id"])
        self.assertEqual(
            set(audit_event),
            {"timestamp", "event", "pairing_id", "phone_id", "phone_key_sha256"},
        )
        self.assertNotIn(self.token, audit_text)
        self.assertNotIn(request["signature"], audit_text)
        self.assertNotIn(request["public_key_der"], audit_text)
        self.assertNotIn("My phone", audit_text)
        self.assertEqual(self.approvals[0][0], "My phone")

    def test_invalid_signature_rejected_without_approval(self) -> None:
        other_key = ec.generate_private_key(ec.SECP256R1())
        status, response = self.service.process_body(self._body(self._request(signature_from=other_key)))
        self.assertEqual((status, response), (400, ERROR_BODY))
        self.assertEqual(self.approvals, [])
        self.assertFalse(self.service.consumed)
        self.assertFalse((self.store_path.parent / "pairing-audit.jsonl").exists())

    def test_invalid_curve_and_malformed_der_rejected(self) -> None:
        non_p256 = ec.generate_private_key(ec.SECP384R1())
        status, response = self.service.process_body(self._body(self._request(key=non_p256)))
        self.assertEqual((status, response), (400, ERROR_BODY))
        self.assertFalse(self.service.consumed)

        malformed = b"not an SPKI key"
        status, response = self.service.process_body(self._body(self._request(der=malformed)))
        self.assertEqual((status, response), (400, ERROR_BODY))
        self.assertFalse(self.service.consumed)

    def test_expired_invitation_rejected(self) -> None:
        expired = self._service(approve=True, now=self.invitation.expires_at)
        status, response = expired.process_body(self._body(self._request()))
        self.assertEqual((status, response), (400, ERROR_BODY))
        self.assertFalse(expired.consumed)
        self.assertEqual(self.approvals, [])

    def test_replay_rejected_after_success(self) -> None:
        body = self._body(self._request())
        self.assertEqual(self.service.process_body(body)[0], 200)
        self.assertEqual(self.service.process_body(body), (400, ERROR_BODY))
        self.assertEqual(len(self.store.records()), 1)

    def test_denial_consumes_invitation_and_does_not_store_key(self) -> None:
        denied = self._service(approve=False)
        body = self._body(self._request())
        self.assertEqual(denied.process_body(body), (400, ERROR_BODY))
        self.assertTrue(denied.consumed)
        self.assertEqual(denied.process_body(body), (400, ERROR_BODY))
        self.assertEqual(self.store.records(), [])
        audit_event = json.loads((self.store_path.parent / "pairing-audit.jsonl").read_text(encoding="utf-8"))
        request = json.loads(body.decode("utf-8"))
        self.assertEqual(audit_event["event"], "approval_denied")
        self.assertEqual(audit_event["phone_id"], request["phone_id"])
        self.assertNotIn(self.token, json.dumps(audit_event))

    def test_audit_log_is_private_and_bounded(self) -> None:
        self.store.record_audit_event(
            "approval_denied",
            self.invitation.pairing_id,
            "a" * 64,
            "a" * 64,
        )
        audit_path = self.store_path.parent / "pairing-audit.jsonl"
        initial = audit_path.read_bytes()
        if __import__("os").name != "nt":
            self.assertEqual(audit_path.stat().st_mode & 0o777, 0o600)
        with patch("pairing_host.server.MAX_AUDIT_LOG_BYTES", len(initial)):
            with self.assertRaisesRegex(RuntimeError, "audit log size limit"):
                self.store.record_audit_event(
                    "approval_granted",
                    self.invitation.pairing_id,
                    "b" * 64,
                    "b" * 64,
                )
        self.assertEqual(audit_path.read_bytes(), initial)

    def test_unexpected_fields_and_oversize_payload_rejected(self) -> None:
        request = self._request()
        request["extra"] = "not allowed"
        self.assertEqual(self.service.process_body(self._body(request)), (400, ERROR_BODY))
        self.assertFalse(self.service.consumed)
        self.assertEqual(
            self.service.process_body(b" " * (MAX_REQUEST_BYTES + 1)),
            (400, ERROR_BODY),
        )

    def test_duplicate_json_keys_are_rejected(self) -> None:
        body = self._body(self._request()).decode("utf-8")
        duplicate = body.replace('"token":', f'"pairing_id":"{self.invitation.pairing_id}","token":', 1)
        self.assertEqual(self.service.process_body(duplicate.encode("utf-8")), (400, ERROR_BODY))
        self.assertFalse(self.service.consumed)
        self.assertEqual(self.approvals, [])

    def test_concurrent_requests_can_consume_invitation_only_once(self) -> None:
        body = self._body(self._request())
        barrier = threading.Barrier(3)
        results: list[int] = []

        def submit() -> None:
            barrier.wait(timeout=2)
            results.append(self.service.process_body(body)[0])

        threads = [threading.Thread(target=submit) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=3)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(sorted(results), [200, 400])
        self.assertEqual(len(self.approvals), 1)
        self.assertEqual(len(self.store.records()), 1)

    def test_corrupt_pairing_store_fails_closed_without_overwrite(self) -> None:
        self.store_path.write_text("corrupt-store", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.store.records()
        with self.assertRaises(RuntimeError):
            self.store.add("0" * 64, b"public-key")
        self.assertEqual(self.store_path.read_text(encoding="utf-8"), "corrupt-store")

    def test_invalid_public_advertise_addresses(self) -> None:
        for value in (
            "example.com",
            "8.8.8.8",
            "127.0.0.1",
            "169.254.1.2",
            "224.0.0.1",
            "::1",
            "fe80::1",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_advertise(value)
        self.assertEqual(str(validate_advertise("192.168.1.20")), "192.168.1.20")
        self.assertEqual(str(validate_advertise("fd00::20")), "fd00::20")

    def test_listener_must_be_exact_advertised_interface(self) -> None:
        advertised = validate_advertise("192.168.1.20")
        self.assertEqual(validate_listen("192.168.1.20", advertised), "192.168.1.20")
        for value in ("0.0.0.0", "192.168.1.21", "::"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_listen(value, advertised)

    def test_names_reject_bidi_formats_and_non_ascii_space_separators(self) -> None:
        for bad_name in ("Phone\u202eName", "Phone\u2007Name"):
            with self.subTest(name=bad_name):
                with self.assertRaises(ValueError):
                    create_invitation(
                        host="192.168.1.20",
                        port=8765,
                        laptop_id=self.laptop_id,
                        laptop_name=bad_name,
                        public_key=self.tls_key.public_key(),
                        now=1000,
                    )
                status, response = self.service.process_body(self._body(self._request(phone_name=bad_name)))
                self.assertEqual((status, response), (400, ERROR_BODY))
                self.assertFalse(self.service.consumed)

    def test_slow_tls_handshake_does_not_block_another_worker(self) -> None:
        class TwoWorkerServer(BoundedThreadingHTTPServer):
            max_workers = 2

            def handle_error(self, request, client_address):
                pass

        httpd = TwoWorkerServer(("127.0.0.1", 0), make_handler(self.service))
        httpd.set_tls_context(build_tls_context(self.certificate, self.tls_key))
        server_thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        server_thread.start()
        address = httpd.server_address
        stalled = socket.create_connection((address[0], address[1]), timeout=1)
        try:
            stalled.settimeout(1)
            time.sleep(0.1)
            client_context = ssl._create_unverified_context()
            started = time.monotonic()
            with client_context.wrap_socket(socket.socket(), server_hostname="127.0.0.1") as client:
                client.settimeout(2)
                client.connect((address[0], address[1]))
                client.sendall(b"GET /not-a-route HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
                response = client.recv(1024)
            self.assertIn(b"404", response)
            self.assertLess(time.monotonic() - started, 2)
        finally:
            stalled.close()
            httpd.shutdown()
            httpd.server_close()
            server_thread.join(timeout=2)

    def test_duplicate_registered_phone_rejected_without_duplicate_record(self) -> None:
        request = self._request()
        self.assertEqual(self.service.process_body(self._body(request))[0], 200)
        next_invitation, next_uri = create_invitation(
            host="192.168.1.20",
            port=8765,
            laptop_id=self.laptop_id,
            laptop_name="Test laptop",
            public_key=self.tls_key.public_key(),
            now=1000,
        )
        second = self._service(approve=True, invitation=next_invitation, store=self.store)
        # Sign the same public identity against the new invitation and use its fresh token.
        request2 = self._request(invitation=next_invitation)
        request2["token"] = dict(parse_qsl(urlsplit(next_uri).query))["token"]
        status, response = second.process_body(self._body(request2))
        self.assertEqual((status, response), (400, ERROR_BODY))
        self.assertEqual(len(self.store.records()), 1)

    def test_tls_identity_has_ip_san_and_invitation_has_exact_query_fields(self) -> None:
        san = self.certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        self.assertIn("192.168.1.20", [str(address) for address in san.get_values_for_type(x509.IPAddress)])
        query = dict(parse_qsl(urlsplit(self.invitation_uri).query, keep_blank_values=True))
        self.assertEqual(
            set(query),
            {"v", "host", "port", "laptop_id", "laptop_name", "pairing_id", "expires_at", "nonce", "token", "spki_sha256"},
        )
        self.assertEqual(query["v"], "1")
        self.assertEqual(len(query["nonce"]), 43)
        self.assertEqual(len(query["token"]), 43)


if __name__ == "__main__":
    unittest.main()
