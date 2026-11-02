#!/usr/bin/env python3
"""Run a bounded local runtime soak without creating an unbounded job backlog."""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUPERVISOR = ROOT / "scripts" / "termux" / "supervisor.sh"


def _request(url: str, *, method: str = "GET", body: dict | None = None) -> tuple[int, dict, float]:
    payload = json.dumps(body, separators=(",", ":")).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json"} if payload is not None else {},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            parsed = json.loads(response.read(8192).decode("utf-8"))
            return response.status, parsed, time.monotonic() - started
    except urllib.error.HTTPError as exc:
        parsed = json.loads(exc.read(8192).decode("utf-8"))
        return exc.code, parsed, time.monotonic() - started


def _rss_kib(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return None


def _disk_free_bytes(path: Path) -> int:
    stat = os.statvfs(path)
    return stat.f_bavail * stat.f_frsize


def _run_supervisor(verb: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SUPERVISOR), verb],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-seconds", type=int, default=3600, help="soak duration (1..86400 seconds)")
    parser.add_argument("--interval-seconds", type=float, default=1.0, help="request interval (0.2..60 seconds)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--report", type=Path, default=None, help="JSONL report path (defaults to the home directory)")
    parser.add_argument("--data-dir", type=Path, default=None, help="private state directory; otherwise a new path is kept under home")
    args = parser.parse_args()
    if not 1 <= args.duration_seconds <= 86400:
        parser.error("--duration-seconds must be between 1 and 86400")
    if not 0.2 <= args.interval_seconds <= 60:
        parser.error("--interval-seconds must be between 0.2 and 60")
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        parser.error("do not run the PocketCloud soak harness as root")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    data_dir = args.data_dir or (Path.home() / ".local" / "share" / f"pocketcloud-soak-{timestamp}-{uuid.uuid4().hex[:8]}")
    data_dir = data_dir.expanduser().resolve()
    home = Path.home().resolve()
    if data_dir == home or home not in data_dir.parents:
        parser.error("soak state directory must be an isolated path under the user's home")
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(data_dir, 0o700)
    report_path = args.report or (Path.home() / f"pocketcloud-soak-{timestamp}.jsonl")
    report_path = report_path.expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHON_BIN"] = sys.executable
    env["PYTHONPATH"] = str(ROOT / "runtime") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["POCKETCLOUD_DATA_DIR"] = str(data_dir)
    env["POCKETCLOUD_PORT"] = str(args.port)
    env.setdefault("POCKETCLOUD_MAX_DATABASE_BYTES", str(32 * 1024 * 1024))
    env.setdefault("POCKETCLOUD_MIN_FREE_BYTES", str(64 * 1024 * 1024))
    base = f"http://127.0.0.1:{args.port}"
    idempotency_key = f"soak:{uuid.uuid4()}"
    latencies: list[float] = []
    failures = 0
    success = False
    started = time.monotonic()
    deadline = started + args.duration_seconds

    start = _run_supervisor("start", env)
    if start.returncode != 0:
        sys.stderr.write(start.stderr or start.stdout)
        return 1
    match = re.search(r"\(pid (\d+)\)", start.stdout)
    pid = int(match.group(1)) if match else -1
    job_id: str | None = None

    try:
        first_status, first_body, first_latency = _request(
            f"{base}/v1/jobs",
            method="POST",
            body={"handler_id": "self_test.v1", "idempotency_key": idempotency_key, "payload": {"message": "soak"}},
        )
        if first_status != 201 or first_body.get("status") != "completed":
            raise RuntimeError(f"initial self-test submission returned an unexpected HTTP/status pair: {first_status}/{first_body.get('status')}")
        job_id = first_body["id"]
        latencies.append(first_latency)

        with report_path.open("w", encoding="utf-8") as report:
            report.write(json.dumps({"event": "start", "time_utc": datetime.now(UTC).isoformat(), "data_dir": str(data_dir), "port": args.port, "duration_seconds": args.duration_seconds, "pid": pid}) + "\n")
            report.flush()
            iteration = 0
            while time.monotonic() < deadline:
                cycle_start = time.monotonic()
                ready_status, ready_body, ready_latency = _request(f"{base}/readyz")
                submit_status, submit_body, submit_latency = _request(
                    f"{base}/v1/jobs",
                    method="POST",
                    body={"handler_id": "self_test.v1", "idempotency_key": idempotency_key, "payload": {"message": "soak"}},
                )
                iteration += 1
                healthy = ready_status == 200 and ready_body.get("status") == "ok"
                deduped = submit_status == 200 and submit_body.get("id") == job_id and submit_body.get("status") == "completed"
                if not healthy or not deduped:
                    failures += 1
                latencies.extend([ready_latency, submit_latency])
                row = {
                    "event": "sample",
                    "time_utc": datetime.now(UTC).isoformat(),
                    "iteration": iteration,
                    "ready_http": ready_status,
                    "idempotent_submit_http": submit_status,
                    "healthy": healthy,
                    "deduplicated": deduped,
                    "rss_kib": _rss_kib(pid) if pid > 0 else None,
                    "database_bytes": (data_dir / "pocketcloud.sqlite3").stat().st_size if (data_dir / "pocketcloud.sqlite3").exists() else None,
                    "free_bytes": _disk_free_bytes(data_dir),
                    "latency_ms": round((ready_latency + submit_latency) * 500, 3),
                }
                report.write(json.dumps(row, separators=(",", ":")) + "\n")
                report.flush()
                remaining = args.interval_seconds - (time.monotonic() - cycle_start)
                if remaining > 0:
                    time.sleep(min(remaining, max(0, deadline - time.monotonic())))

            report.write(json.dumps({
                "event": "summary",
                "time_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "iterations": iteration,
                "failures": failures,
                "latency_samples": len(latencies),
                "p50_ms": round(statistics.median(latencies) * 1000, 2) if latencies else None,
                "p95_ms": round(sorted(latencies)[int((len(latencies) - 1) * 0.95)] * 1000, 2) if latencies else None,
                "data_dir": str(data_dir),
            }, separators=(",", ":")) + "\n")
            report.flush()
        success = failures == 0
    except Exception as exc:
        print(f"soak failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        success = False
    finally:
        stop = _run_supervisor("stop", env)
        if stop.returncode != 0:
            sys.stderr.write(stop.stderr or stop.stdout)
            success = False

    print(f"Report: {report_path}")
    print(f"Test state retained for inspection: {data_dir}")
    print(f"Result: {'PASS' if success else 'FAIL'}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
