from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = str(REPOSITORY_ROOT / "runtime")
if RUNTIME_PATH not in sys.path:
    sys.path.insert(0, RUNTIME_PATH)

from pocketcloud.db import create_sqlite_engine
from pocketcloud.config import load_settings, require_unprivileged
from pocketcloud.storage import database_bytes


class RuntimeIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="pocketcloud-test-", dir=Path.home())
        self.data_dir = Path(self.temporary.name) / "private-data"
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.process: subprocess.Popen[bytes] | None = None
        self.log_path = Path(self.temporary.name) / "server.log"
        self.startup_overrides: dict[str, str] = {}
        self._start_server()

    def tearDown(self) -> None:
        self._stop_server()
        self.temporary.cleanup()

    def _start_server(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = RUNTIME_PATH + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        env["POCKETCLOUD_DATA_DIR"] = str(self.data_dir)
        env["POCKETCLOUD_PORT"] = str(self.port)
        env["PYTHON_BIN"] = sys.executable
        env.update(self.startup_overrides)
        log_file = self.log_path.open("ab")
        self.process = subprocess.Popen(
            ["bash", "scripts/termux/run.sh"],
            cwd=REPOSITORY_ROOT,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        self._server_log_handle = log_file
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail(f"PocketCloud exited during startup; log: {self.log_path.read_text(errors='replace')}")
            try:
                self._get("/readyz")
                return
            except (URLError, TimeoutError):
                time.sleep(0.1)
        self.fail(f"PocketCloud did not become ready; log: {self.log_path.read_text(errors='replace')}")

    def _stop_server(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if hasattr(self, "_server_log_handle"):
            self._server_log_handle.close()
        self.process = None

    def _get(self, path: str) -> dict[str, object]:
        with urlopen(self.base_url + path, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post(self, path: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as response:
            return response.code, json.loads(response.read().decode("utf-8"))

    def test_health_separates_liveness_and_database_readiness(self) -> None:
        self.assertEqual(self._get("/livez")["status"], "ok")
        self.assertEqual(self._get("/readyz")["status"], "ok")

    def test_root_execution_is_rejected(self) -> None:
        with patch("pocketcloud.config.os.geteuid", return_value=0):
            with self.assertRaisesRegex(RuntimeError, "must not run as root"):
                require_unprivileged()

    def test_external_state_directory_is_rejected(self) -> None:
        with patch.dict(os.environ, {"POCKETCLOUD_DATA_DIR": "/tmp/pocketcloud-external-state"}):
            with self.assertRaisesRegex(PermissionError, "under the current user's home directory"):
                load_settings()

    def test_storage_reserve_rejects_new_jobs_without_dropping_state(self) -> None:
        self._stop_server()
        self.startup_overrides["POCKETCLOUD_MIN_FREE_BYTES"] = str(10**18)
        self._start_server()
        status, body = self._post(
            "/v1/jobs",
            {"handler_id": "self_test.v1", "idempotency_key": "storage:rejected", "payload": {"message": "x"}},
        )
        self.assertEqual(status, 507)
        self.assertEqual(body["detail"], "recovery_space_reserved")
        with sqlite3.connect(self.data_dir / "pocketcloud.sqlite3") as connection:
            count = connection.execute(
                "SELECT count(*) FROM jobs WHERE idempotency_key='storage:rejected'"
            ).fetchone()[0]
        self.assertEqual(count, 0)

        self._stop_server()
        self.startup_overrides.clear()
        self.startup_overrides["POCKETCLOUD_MAX_DATABASE_BYTES"] = "1"
        self._start_server()
        status, body = self._post(
            "/v1/jobs",
            {"handler_id": "self_test.v1", "idempotency_key": "storage:db-cap", "payload": {"message": "x"}},
        )
        self.assertEqual(status, 507)
        self.assertEqual(body["detail"], "database_quota_reached")
        with sqlite3.connect(self.data_dir / "pocketcloud.sqlite3") as connection:
            count = connection.execute(
                "SELECT count(*) FROM jobs WHERE idempotency_key='storage:db-cap'"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_concurrent_submissions_are_admitted_against_updated_database_usage(self) -> None:
        self._stop_server()
        current_bytes = database_bytes(self.data_dir / "pocketcloud.sqlite3")
        self.startup_overrides.clear()
        self.startup_overrides["POCKETCLOUD_MAX_DATABASE_BYTES"] = str(current_bytes + 20_000)
        self.startup_overrides["POCKETCLOUD_MIN_FREE_BYTES"] = "0"
        self._start_server()

        def submit(index: int) -> tuple[int, dict[str, object]]:
            return self._post(
                "/v1/jobs",
                {
                    "handler_id": "self_test.v1",
                    "idempotency_key": f"parallel:{index}",
                    "payload": {"message": "x"},
                },
            )

        with ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(submit, range(12)))
        statuses = [status for status, _ in results]
        self.assertIn(201, statuses)
        self.assertIn(507, statuses)
        self.assertTrue(all(status in (201, 507) for status in statuses))
        created = sum(status == 201 for status in statuses)
        with sqlite3.connect(self.data_dir / "pocketcloud.sqlite3") as connection:
            persisted = connection.execute(
                "SELECT count(*) FROM jobs WHERE idempotency_key LIKE 'parallel:%'"
            ).fetchone()[0]
        self.assertEqual(persisted, created)

    def test_second_runtime_cannot_quarantine_jobs_while_owner_is_alive(self) -> None:
        status, job = self._post(
            "/v1/jobs",
            {"handler_id": "self_test.v1", "idempotency_key": "lock:probe", "payload": {"message": "x"}},
        )
        self.assertEqual(status, 201)
        with sqlite3.connect(self.data_dir / "pocketcloud.sqlite3") as connection:
            connection.execute("UPDATE jobs SET status='running' WHERE id=?", (job["id"],))

        env = os.environ.copy()
        env["PYTHONPATH"] = RUNTIME_PATH + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        env["PYTHON_BIN"] = sys.executable
        env["POCKETCLOUD_DATA_DIR"] = str(self.data_dir)
        env["POCKETCLOUD_PORT"] = str(self.port + 1)
        result = subprocess.run(
            ["bash", "scripts/termux/run.sh"],
            cwd=REPOSITORY_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("another PocketCloud runtime already owns this data directory", result.stderr)
        self.assertEqual(self._get(f"/v1/jobs/{job['id']}")["status"], "running")

    def test_sqlite_uses_wal_foreign_keys_busy_timeout_and_private_data_directory(self) -> None:
        database_path = self.data_dir / "pocketcloud.sqlite3"
        with sqlite3.connect(database_path) as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
        database_limit = 64 * 1024 * 1024
        engine = create_sqlite_engine(f"sqlite:///{database_path}", max_database_bytes=database_limit)
        with engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one(), 1)
            self.assertEqual(connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one(), 10000)
            self.assertEqual(connection.exec_driver_sql("PRAGMA synchronous").scalar_one(), 2)
            page_size = connection.exec_driver_sql("PRAGMA page_size").scalar_one()
            self.assertEqual(
                connection.exec_driver_sql("PRAGMA max_page_count").scalar_one(), database_limit // page_size
            )
        engine.dispose()
        self.assertEqual(self.data_dir.stat().st_mode & 0o777, 0o700)
        self.assertEqual(database_path.stat().st_mode & 0o777, 0o600)

    def test_request_body_limit_is_enforced_before_schema_parsing(self) -> None:
        status, body = self._post(
            "/v1/jobs",
            {"handler_id": "self_test.v1", "idempotency_key": "large", "payload": {"message": "x" * 9000}},
        )
        self.assertEqual(status, 413)
        self.assertEqual(body["detail"], "request_too_large")

    def test_job_is_committed_idempotent_and_survives_process_restart(self) -> None:
        submission = {
            "handler_id": "self_test.v1",
            "idempotency_key": "test:durable-1",
            "payload": {"message": "durable hello"},
        }
        status, created = self._post("/v1/jobs", submission)
        self.assertEqual(status, 201)
        self.assertEqual(created["status"], "completed")
        self.assertEqual(created["result"], {"handler": "self_test.v1", "echo": "durable hello"})

        duplicate_status, duplicate = self._post("/v1/jobs", submission)
        self.assertEqual(duplicate_status, 200)
        self.assertEqual(duplicate["id"], created["id"])

        conflict = dict(submission)
        conflict["payload"] = {"message": "changed input"}
        conflict_status, conflict_body = self._post("/v1/jobs", conflict)
        self.assertEqual(conflict_status, 409)
        self.assertEqual(conflict_body["detail"], "idempotency_key_reused_with_different_payload")

        self._stop_server()
        self._start_server()
        restored = self._get(f"/v1/jobs/{created['id']}")
        self.assertEqual(restored["status"], "completed")
        self.assertEqual(restored["result"], created["result"])

    def test_invalid_handler_is_rejected_and_interrupted_work_is_quarantined(self) -> None:
        invalid_status, _ = self._post(
            "/v1/jobs",
            {"handler_id": "shell", "idempotency_key": "test:no-shell", "payload": {"message": "x"}},
        )
        self.assertEqual(invalid_status, 422)

        status, created = self._post(
            "/v1/jobs",
            {"handler_id": "self_test.v1", "idempotency_key": "test:interrupted", "payload": {"message": "safe"}},
        )
        self.assertEqual(status, 201)
        db_path = self.data_dir / "pocketcloud.sqlite3"
        with sqlite3.connect(db_path) as connection:
            connection.execute("UPDATE jobs SET status='running' WHERE id=?", (created["id"],))

        self._stop_server()
        self._start_server()
        restored = self._get(f"/v1/jobs/{created['id']}")
        self.assertEqual(restored["status"], "needs_reconciliation")
        self.assertEqual(restored["error_code"], "process_interrupted")
        self.assertEqual(restored["events"][-1]["diagnostic_code"], "process_interrupted")


if __name__ == "__main__":
    unittest.main(verbosity=2)
