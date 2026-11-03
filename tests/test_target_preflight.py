from __future__ import annotations

import sys
import os
import stat
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TESTING_PATH = str(REPOSITORY_ROOT / "scripts" / "testing")
if TESTING_PATH not in sys.path:
    sys.path.insert(0, TESTING_PATH)

from target_preflight import PreflightError, _write_private_new_file, collect_profile


SERIAL = "DEVICE-SERIAL-DO-NOT-RECORD"
PROPERTIES = {
    "ro.product.manufacturer": "Google",
    "ro.product.model": "Pixel 8a",
    "ro.product.device": "akita",
    "ro.soc.manufacturer": "Google",
    "ro.soc.model": "Tensor G3",
    "ro.build.version.release": "16",
    "ro.build.version.sdk": "36",
    "ro.build.version.security_patch": "2026-10-05",
    "ro.build.fingerprint": "google/akita/akita:16/ABC123/1234567:user/release-keys",
    "ro.product.cpu.abi": "arm64-v8a",
    "ro.product.cpu.abilist": "arm64-v8a,armeabi-v7a,armeabi",
    "ro.kernel.qemu": "0",
}


class FakeAdb:
    def __init__(self, *, devices: str | None = None, properties: dict[str, str] | None = None, termux: str | None = None):
        self.devices = devices or f"List of devices attached\n{SERIAL} device product:akita model:Pixel_8a device:akita transport_id:1\n"
        self.properties = dict(PROPERTIES if properties is None else properties)
        self.termux = termux if termux is not None else "Package [com.termux] (123):\n  versionCode=1023 minSdk=24 targetSdk=28\n  versionName=0.118.3\n"
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, argv: list[str], **kwargs: object) -> CompletedProcess[str]:
        self.calls.append((list(argv), dict(kwargs)))
        if argv[1:] == ["version"]:
            return CompletedProcess(argv, 0, "Android Debug Bridge version 1.0.41\n", "")
        if argv[1:] == ["devices", "-l"]:
            return CompletedProcess(argv, 0, self.devices, "")
        if "shell" not in argv:
            return CompletedProcess(argv, 2, "", "unexpected adb command")
        remote = argv[argv.index("shell") + 1 :]
        if remote[:1] == ["getprop"] and len(remote) == 2:
            return CompletedProcess(argv, 0, self.properties.get(remote[1], "") + "\n", "")
        if remote == ["cat", "/proc/meminfo"]:
            return CompletedProcess(argv, 0, "MemTotal:        8123456 kB\nMemFree:          123456 kB\n", "")
        if remote == ["df", "-k", "/data"]:
            return CompletedProcess(argv, 0, "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/block/dm-55 100000000 20000000 80000000 20% /data\n", "")
        if remote == ["dumpsys", "package", "com.termux"]:
            if self.termux is None:
                return CompletedProcess(argv, 1, "", "Can't find service: package com.termux")
            return CompletedProcess(argv, 0, self.termux, "")
        return CompletedProcess(argv, 2, "", f"unexpected remote argv: {remote!r}")


class TargetPreflightTests(unittest.TestCase):
    def test_collects_read_only_profile_without_recording_device_serial(self) -> None:
        fake = FakeAdb()
        profile = collect_profile("fake-adb", runner=fake)

        self.assertEqual(profile["schema_version"], 1)
        self.assertEqual(profile["device"]["manufacturer"], {"status": "observed", "value": "Google"})
        self.assertEqual(profile["device"]["model"]["value"], "Pixel 8a")
        self.assertEqual(profile["device"]["api_level"]["value"], 36)
        self.assertEqual(profile["device"]["total_memory_bytes"]["value"], 8123456 * 1024)
        self.assertEqual(profile["device"]["data_available_bytes"]["value"], 80000000 * 1024)
        self.assertEqual(profile["device"]["termux_version"]["value"], "0.118.3")
        self.assertTrue(profile["inventory"]["complete"])
        self.assertEqual(profile["gate_status"], "not_evaluated")
        self.assertNotIn(SERIAL, repr(profile))

        remote_commands = [argv[argv.index("shell") + 1 :] for argv, _ in fake.calls if "shell" in argv]
        self.assertTrue(remote_commands)
        self.assertTrue(all(command[0] in {"getprop", "cat", "df", "dumpsys"} for command in remote_commands))
        self.assertFalse(any("install" in command or "force-stop" in command for command in remote_commands))
        for _, kwargs in fake.calls:
            self.assertNotIn("shell", kwargs)
            self.assertEqual(kwargs["timeout"], 10)

    def test_multiple_connected_devices_require_explicit_serial(self) -> None:
        fake = FakeAdb(devices=(
            "List of devices attached\n"
            "phone-1 device product:a model:A device:a transport_id:1\n"
            "phone-2 device product:b model:B device:b transport_id:2\n"
        ))
        with self.assertRaisesRegex(PreflightError, "more than one authorized device"):
            collect_profile("fake-adb", runner=fake)
        self.assertFalse(any("shell" in argv for argv, _ in fake.calls))

    def test_explicit_serial_selects_one_device_but_is_not_written_to_profile(self) -> None:
        fake = FakeAdb(devices=(
            "List of devices attached\n"
            "phone-1 device product:a model:A device:a transport_id:1\n"
            f"{SERIAL} device product:akita model:Pixel_8a device:akita transport_id:2\n"
        ))
        profile = collect_profile("fake-adb", serial=SERIAL, runner=fake)
        self.assertTrue(profile["inventory"]["complete"])
        self.assertNotIn(SERIAL, repr(profile))
        self.assertTrue(any(argv[1:4] == ["-s", SERIAL, "shell"] for argv, _ in fake.calls))

    def test_missing_termux_is_reported_as_incomplete_not_silently_ignored(self) -> None:
        profile = collect_profile("fake-adb", runner=FakeAdb(termux=""))
        self.assertFalse(profile["inventory"]["complete"])
        self.assertIn("termux_version", profile["inventory"]["missing_required_fields"])
        self.assertEqual(profile["device"]["termux_version"]["status"], "unavailable")
        self.assertEqual(profile["gate_status"], "not_evaluated")

    def test_emulator_property_is_recorded_as_a_hint_not_target_device_proof(self) -> None:
        properties = dict(PROPERTIES)
        properties["ro.kernel.qemu"] = "1"
        profile = collect_profile("fake-adb", runner=FakeAdb(properties=properties))
        self.assertEqual(profile["device_kind"]["value"], "reported_emulator")
        self.assertEqual(profile["gate_status"], "not_evaluated")
        self.assertTrue(any("does not prove physical hardware" in item for item in profile["limitations"]))

    def test_oversized_adb_output_is_rejected(self) -> None:
        class Oversized(FakeAdb):
            def __call__(self, argv: list[str], **kwargs: object) -> CompletedProcess[str]:
                if "shell" in argv and argv[argv.index("shell") + 1 :] == ["getprop", "ro.product.model"]:
                    return CompletedProcess(argv, 0, "x" * (1024 * 1024 + 1), "")
                return super().__call__(argv, **kwargs)

        with self.assertRaisesRegex(PreflightError, "output limit"):
            collect_profile("fake-adb", runner=Oversized())

    def test_unavailable_or_unauthorized_device_fails_without_remote_queries(self) -> None:
        fake = FakeAdb(devices="List of devices attached\nphone-1 unauthorized usb:1-1\n")
        with self.assertRaisesRegex(PreflightError, "no authorized Android device"):
            collect_profile("fake-adb", runner=fake)
        self.assertFalse(any("shell" in argv for argv, _ in fake.calls))

    def test_report_file_is_private_and_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            _write_private_new_file(path, "{}\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "{}\n")
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                _write_private_new_file(path, "changed\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "{}\n")


if __name__ == "__main__":
    unittest.main()
