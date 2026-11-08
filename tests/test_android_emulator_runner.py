import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNNER_SOURCE = REPOSITORY_ROOT / "scripts/testing/run_android_emulator_tests.sh"


class AndroidEmulatorRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pocketcloud-avd-runner-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fake_repo = self.root / "repo"
        self.runner = self.fake_repo / "scripts/testing/run_android_emulator_tests.sh"
        self.runner.parent.mkdir(parents=True)
        shutil.copy2(RUNNER_SOURCE, self.runner)
        self.supervisor = self.fake_repo / "android-supervisor"
        self.supervisor.mkdir()
        self.sdk = self.root / "sdk"
        self.home = self.root / "home"
        self.runner_temp = self.root / "runner-temp"
        self.marker = self.root / "gradle-reached.txt"
        for directory in (
            self.sdk / "platform-tools",
            self.sdk / "cmdline-tools/latest/bin",
            self.sdk / "emulator",
            self.home,
            self.runner_temp,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        self._executable(
            self.sdk / "platform-tools/adb",
            """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == start-server ]]; then exit 0; fi
if [[ "$1" == -s && "$3" == wait-for-device ]]; then exit 0; fi
if [[ "$1" == -s && "$3" == shell && "$4" == getprop ]]; then
  case "$5" in
    sys.boot_completed) echo 1 ;;
    ro.build.version.sdk) echo "$POCKETCLOUD_AVD_API_LEVEL" ;;
    ro.kernel.qemu) echo 1 ;;
    *) exit 2 ;;
  esac
  exit 0
fi
echo "unexpected adb call: $*" >&2
exit 3
""",
        )
        self._executable(
            self.sdk / "cmdline-tools/latest/bin/avdmanager",
            """#!/usr/bin/env bash
set -euo pipefail
if [[ -v ANDROID_SDK_HOME ]]; then
  echo 'deprecated ANDROID_SDK_HOME was not unset' >&2
  exit 5
fi
if [[ "$1 $2" == 'create avd' ]]; then
  if [[ "${MOCK_AVDMANAGER_CREATE_FAIL:-0}" == 1 ]]; then
    echo 'mock AVD creation failure' >&2
    exit 9
  fi
  name=''
  while (($#)); do
    if [[ "$1" == -n ]]; then name="$2"; shift 2; else shift; fi
  done
  test -n "$name"
  mkdir -p "$ANDROID_AVD_HOME/$name.avd"
  printf 'path=%s\n' "$ANDROID_AVD_HOME/$name.avd" > "$ANDROID_AVD_HOME/$name.ini"
  printf 'AvdId=%s\n' "$name" > "$ANDROID_AVD_HOME/$name.avd/config.ini"
  exit 0
fi
if [[ "$1 $2" == 'list avd' ]]; then echo 'fake AVD list'; exit 0; fi
if [[ "$1 $2" == 'list device' ]]; then echo 'fake device profile'; exit 0; fi
exit 6
""",
        )
        self._executable(
            self.sdk / "emulator/emulator",
            """#!/usr/bin/env bash
case "$1" in
  -accel-check) echo accel; exit 0 ;;
  -version) echo 'Android emulator fake 1'; exit 0 ;;
  -avd) exec sleep 120 ;;
esac
exit 2
""",
        )
        self._executable(
            self.supervisor / "gradlew",
            """#!/usr/bin/env bash
printf '%s\n' "$*" > "$POCKETCLOUD_MOCK_GRADLE_MARKER"
""",
        )

    @staticmethod
    def _executable(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def _environment(self, api_level: str) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "ANDROID_HOME": str(self.sdk),
                "ANDROID_SDK_ROOT": str(self.sdk),
                "ANDROID_SDK_HOME": str(self.root / "legacy-android-home"),
                "HOME": str(self.home),
                "POCKETCLOUD_AVD_API_LEVEL": api_level,
                "POCKETCLOUD_MOCK_GRADLE_MARKER": str(self.marker),
                "RUNNER_TEMP": str(self.runner_temp),
            }
        )
        env.pop("ANDROID_USER_HOME", None)
        env.pop("ANDROID_EMULATOR_HOME", None)
        env.pop("ANDROID_AVD_HOME", None)
        return env

    def _run(self, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(self.runner)],
            cwd=self.fake_repo,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )

    def test_creates_avd_checks_identity_and_runs_instrumentation_command(self):
        result = self._run(self._environment("36"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"Android user home: {self.home}/.android", result.stdout)
        self.assertIn("AVD ready: serial=emulator-5554 api=36 reported_emulator=1", result.stdout)
        self.assertTrue((self.home / ".android/avd/pocketcloud-api36.ini").is_file())
        self.assertTrue((self.home / ".android/avd/pocketcloud-api36.avd/config.ini").is_file())
        self.assertEqual(self.marker.read_text(encoding="utf-8").strip(), "--no-daemon connectedDebugAndroidTest")

    def test_creation_failure_prints_diagnostics_and_does_not_run_gradle(self):
        env = self._environment("29")
        env["MOCK_AVDMANAGER_CREATE_FAIL"] = "1"
        result = self._run(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AVD creation failed; available hardware profiles", result.stderr)
        self.assertIn("fake device profile", result.stderr)
        self.assertIn("Existing AVDs", result.stderr)
        self.assertFalse(self.marker.exists())


if __name__ == "__main__":
    unittest.main()
