#!/usr/bin/env python3
"""Collect a bounded, read-only Android target inventory through caller-supplied adb."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

MAX_CAPTURE_BYTES = 1024 * 1024
MAX_PROPERTY_LENGTH = 4096
COMMAND_TIMEOUT_SECONDS = 10
PROPERTY_KEYS = {
    "manufacturer": "ro.product.manufacturer",
    "model": "ro.product.model",
    "device_codename": "ro.product.device",
    "soc_manufacturer": "ro.soc.manufacturer",
    "soc_model": "ro.soc.model",
    "android_release": "ro.build.version.release",
    "api_level": "ro.build.version.sdk",
    "security_patch": "ro.build.version.security_patch",
    "build_fingerprint": "ro.build.fingerprint",
    "primary_abi": "ro.product.cpu.abi",
    "supported_abis": "ro.product.cpu.abilist",
    "qemu_property": "ro.kernel.qemu",
}
REQUIRED_FIELDS = (
    "manufacturer",
    "model",
    "android_release",
    "api_level",
    "primary_abi",
    "supported_abis",
    "total_memory_bytes",
    "data_available_bytes",
    "termux_version",
)

Runner = Callable[..., subprocess.CompletedProcess[str]]


class PreflightError(RuntimeError):
    """A safe target inventory could not be collected unambiguously."""


class OutputLimitError(PreflightError):
    """An ADB response exceeded the collector's bounded-output contract."""


def _invoke(
    adb: str,
    arguments: list[str],
    *,
    serial: str | None,
    runner: Runner,
) -> str:
    argv = [adb]
    if serial is not None:
        argv.extend(["-s", serial])
    argv.extend(arguments)
    try:
        result = runner(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise PreflightError("adb executable was not found; install Android platform-tools and provide adb on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise PreflightError("adb command exceeded the 10-second preflight timeout") from exc
    except OSError as exc:
        raise PreflightError(f"could not execute adb: {exc}") from exc

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    output_size = len(stdout.encode("utf-8", errors="replace")) + len(stderr.encode("utf-8", errors="replace"))
    if output_size > MAX_CAPTURE_BYTES:
        raise OutputLimitError("adb output limit exceeded; no profile was accepted")
    if result.returncode != 0:
        action = " ".join(arguments[:3])
        raise PreflightError(f"adb command failed ({action or 'probe'}, exit {result.returncode})")
    return stdout


def _select_serial(devices_output: str, requested_serial: str | None) -> str:
    rows: list[tuple[str, str]] = []
    in_table = False
    for line in devices_output.splitlines():
        if line.strip() == "List of devices attached":
            in_table = True
            continue
        if not in_table:
            continue
        parts = line.split()
        if len(parts) >= 2:
            rows.append((parts[0], parts[1]))
    if not in_table:
        raise PreflightError("adb did not return a recognizable device list")

    authorized = [serial for serial, state in rows if state == "device"]
    if requested_serial is not None:
        if requested_serial not in authorized:
            raise PreflightError("the explicitly selected serial is not an authorized, online Android device")
        return requested_serial
    if not authorized:
        raise PreflightError("no authorized Android device is connected; unlock it and approve its ADB key")
    if len(authorized) != 1:
        raise PreflightError("more than one authorized device is connected; select exactly one with --serial")
    return authorized[0]


def _observed(value: str) -> dict[str, object]:
    return {"status": "observed", "value": value}


def _unavailable(reason: str) -> dict[str, object]:
    return {"status": "unavailable", "reason": reason}


def _read_property(adb: str, serial: str, key: str, runner: Runner) -> dict[str, object]:
    try:
        value = _invoke(adb, ["shell", "getprop", key], serial=serial, runner=runner).strip()
    except OutputLimitError:
        raise
    except PreflightError:
        return _unavailable("adb_probe_failed")
    if not value:
        return _unavailable("property_empty_or_unsupported")
    if len(value) > MAX_PROPERTY_LENGTH:
        return _unavailable("property_length_limit")
    return _observed(value)


def _read_memory(adb: str, serial: str, runner: Runner) -> dict[str, object]:
    try:
        output = _invoke(adb, ["shell", "cat", "/proc/meminfo"], serial=serial, runner=runner)
    except OutputLimitError:
        raise
    except PreflightError:
        return _unavailable("meminfo_unavailable")
    match = re.search(r"^MemTotal:\s+(\d+)\s+kB\s*$", output, re.MULTILINE)
    if not match:
        return _unavailable("memtotal_missing_or_unparseable")
    return {"status": "observed", "value": int(match.group(1)) * 1024, "source": "/proc/meminfo:MemTotal"}


def _read_data_free(adb: str, serial: str, runner: Runner) -> dict[str, object]:
    try:
        output = _invoke(adb, ["shell", "df", "-k", "/data"], serial=serial, runner=runner)
    except OutputLimitError:
        raise
    except PreflightError:
        return _unavailable("data_partition_unavailable")
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[-1] == "/data":
            try:
                return {"status": "observed", "value": int(parts[3]) * 1024, "source": "df -k /data:Available"}
            except ValueError:
                break
    return _unavailable("data_partition_free_space_missing_or_unparseable")


def _read_termux_version(adb: str, serial: str, runner: Runner) -> dict[str, object]:
    try:
        output = _invoke(
            adb,
            ["shell", "dumpsys", "package", "com.termux"],
            serial=serial,
            runner=runner,
        )
    except OutputLimitError:
        raise
    except PreflightError:
        return _unavailable("Termux package unavailable or package query failed")
    match = re.search(r"^\s*versionName=([^\s]+)", output, re.MULTILINE)
    if not match:
        return _unavailable("Termux version name not exposed by package manager")
    return {"status": "observed", "value": match.group(1), "package": "com.termux"}


def collect_profile(
    adb: str = "adb",
    *,
    serial: str | None = None,
    runner: Runner | None = None,
) -> dict[str, object]:
    """Collect an inventory only; never install, launch, stop, or modify a device."""
    run = runner or subprocess.run
    if not adb.strip():
        raise PreflightError("adb command cannot be empty")
    version_output = _invoke(adb, ["version"], serial=None, runner=run)
    version_line = next((line.strip() for line in version_output.splitlines() if line.strip()), "")
    if not version_line:
        raise PreflightError("adb version output was empty")
    devices_output = _invoke(adb, ["devices", "-l"], serial=None, runner=run)
    selected_serial = _select_serial(devices_output, serial)

    device: dict[str, dict[str, object]] = {
        name: _read_property(adb, selected_serial, key, run)
        for name, key in PROPERTY_KEYS.items()
    }
    api = device["api_level"]
    if api["status"] == "observed":
        try:
            api["value"] = int(str(api["value"]))
        except ValueError:
            device["api_level"] = _unavailable("api_level_not_an_integer")

    abi_list = device["supported_abis"]
    if abi_list["status"] == "observed":
        abi_list["value"] = [part for part in str(abi_list["value"]).split(",") if part]
        if not abi_list["value"]:
            device["supported_abis"] = _unavailable("abi_list_empty")

    device["total_memory_bytes"] = _read_memory(adb, selected_serial, run)
    device["data_available_bytes"] = _read_data_free(adb, selected_serial, run)
    device["termux_version"] = _read_termux_version(adb, selected_serial, run)

    missing = [name for name in REQUIRED_FIELDS if device[name]["status"] != "observed"]
    qemu = device["qemu_property"]
    if qemu["status"] != "observed":
        device_kind = _unavailable("emulator_property_unavailable")
    elif qemu["value"] == "1":
        device_kind = {"status": "observed", "value": "reported_emulator", "basis": "ro.kernel.qemu"}
    else:
        device_kind = {
            "status": "observed",
            "value": "not_reported_as_emulator",
            "basis": "ro.kernel.qemu",
        }

    return {
        "schema_version": 1,
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "collector": "PocketCloud read-only Android ADB preflight",
        "adb_client": {"version": version_line},
        "device": device,
        "device_kind": device_kind,
        "inventory": {
            "status": "complete" if not missing else "incomplete",
            "complete": not missing,
            "missing_required_fields": missing,
        },
        "gate_status": "not_evaluated",
        "limitations": [
            "Inventory only: this does not test Termux RUN_COMMAND, supervisor lifecycle, pairing, resource policy, or release behavior.",
            "The selected ADB serial is intentionally omitted from the report.",
            "ro.kernel.qemu is only a reported build property; it does not prove physical hardware or prove an emulator's fidelity.",
            "OEM background restrictions, battery capacity, thermal behavior, and user-granted Termux settings require separate checks.",
            "ADB may start its host-side server when listing devices; this collector issues no device install, launch, stop, write, or root command.",
        ],
    }


def _write_private_new_file(path: Path, content: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default=os.environ.get("POCKETCLOUD_ADB", "adb"), help="adb executable or path")
    parser.add_argument("--serial", default=None, help="select one authorized device when multiple are connected")
    parser.add_argument("--output", type=Path, default=None, help="write a new private JSON report without overwriting an existing file")
    args = parser.parse_args(argv)
    resolved_adb = shutil.which(args.adb) if os.path.sep not in args.adb else args.adb
    if not resolved_adb:
        print("preflight blocked: adb executable was not found; install Android platform-tools or set --adb", file=sys.stderr)
        return 2
    try:
        profile = collect_profile(resolved_adb, serial=args.serial)
        rendered = json.dumps(profile, ensure_ascii=True, indent=2) + "\n"
        if args.output is None:
            sys.stdout.write(rendered)
        else:
            try:
                _write_private_new_file(args.output, rendered)
            except FileExistsError:
                raise PreflightError("report path already exists; choose a new path rather than overwrite evidence")
            except OSError as exc:
                raise PreflightError(f"could not write the report: {exc}") from exc
            print(f"Local report written: {args.output}", file=sys.stderr)
        return 0 if profile["inventory"]["complete"] else 1
    except PreflightError as exc:
        print(f"preflight blocked: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
