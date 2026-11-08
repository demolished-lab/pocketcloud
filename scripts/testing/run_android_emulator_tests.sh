#!/usr/bin/env bash
set -euo pipefail

api_level="${POCKETCLOUD_AVD_API_LEVEL:-36}"
case "$api_level" in
  29|36) ;;
  *) echo "unsupported AVD API level: $api_level (supported test profiles: 29, 36)" >&2; exit 2 ;;
esac

sdk_root="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$sdk_root" ]]; then
  echo "ANDROID_SDK_ROOT or ANDROID_HOME must point to an installed Android SDK" >&2
  exit 2
fi

adb_bin="$sdk_root/platform-tools/adb"
avdmanager_bin="$sdk_root/cmdline-tools/latest/bin/avdmanager"
emulator_bin="$sdk_root/emulator/emulator"
[[ -x "$adb_bin" ]] || adb_bin="$(command -v adb 2>/dev/null || true)"
[[ -x "$avdmanager_bin" ]] || avdmanager_bin="$(command -v avdmanager 2>/dev/null || true)"
[[ -x "$emulator_bin" ]] || emulator_bin="$(command -v emulator 2>/dev/null || true)"
for tool_path in "$adb_bin" "$avdmanager_bin" "$emulator_bin"; do
  if [[ ! -x "$tool_path" ]]; then
    echo "required Android SDK command is not executable: $tool_path" >&2
    exit 2
  fi
done

if ! "$emulator_bin" -accel-check; then
  echo "Android Emulator VM acceleration is required for this bounded AVD test" >&2
  exit 2
fi
"$emulator_bin" -version

avd_name="pocketcloud-api${api_level}"
system_image="system-images;android-${api_level};google_apis;x86_64"
android_user_home="$HOME/.android"
unset ANDROID_SDK_HOME
export ANDROID_USER_HOME="$android_user_home"
export ANDROID_EMULATOR_HOME="$android_user_home"
export ANDROID_AVD_HOME="$android_user_home/avd"
mkdir -p "$ANDROID_AVD_HOME"
printf 'Android user home: %s\nAndroid emulator home: %s\nAndroid AVD home: %s\n' "$ANDROID_USER_HOME" "$ANDROID_EMULATOR_HOME" "$ANDROID_AVD_HOME"
if ! printf 'no\n' | "$avdmanager_bin" create avd -f -n "$avd_name" -k "$system_image"; then
  echo "AVD creation failed; available hardware profiles:" >&2
  "$avdmanager_bin" list device -c >&2 || true
  echo "Existing AVDs:" >&2
  "$avdmanager_bin" list avd >&2 || true
  find "$ANDROID_USER_HOME" -maxdepth 4 -iname "*${avd_name}*" -print >&2 || true
  exit 1
fi
"$avdmanager_bin" list avd
if [[ ! -f "$ANDROID_AVD_HOME/$avd_name.ini" || ! -f "$ANDROID_AVD_HOME/$avd_name.avd/config.ini" ]]; then
  echo "avdmanager did not create the expected profile files under $ANDROID_AVD_HOME" >&2
  find "$ANDROID_AVD_HOME" -maxdepth 2 -type f -print >&2 || true
  exit 1
fi

log_dir="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
log_file="$log_dir/pocketcloud-emulator-api${api_level}.log"
mkdir -p "$log_dir"
"$emulator_bin" -avd "$avd_name" -port 5554 -no-window -no-audio -no-boot-anim -no-snapshot -wipe-data -accel on -gpu swiftshader >"$log_file" 2>&1 &
emulator_pid=$!

cleanup() {
  status=$?
  trap - EXIT
  if kill -0 "$emulator_pid" 2>/dev/null; then
    kill "$emulator_pid" 2>/dev/null || true
    wait "$emulator_pid" 2>/dev/null || true
  fi
  if (( status != 0 )); then
    echo "--- Android Emulator log ($log_file) ---" >&2
    tail -n 120 "$log_file" >&2 || true
  fi
  exit "$status"
}
trap cleanup EXIT

"$adb_bin" start-server
serial="emulator-5554"
if ! timeout 300 "$adb_bin" -s "$serial" wait-for-device; then
  echo "ADB did not discover the emulator within 300 seconds" >&2
  exit 1
fi
boot_deadline=$((SECONDS + 300))
while [[ "$("$adb_bin" -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" != "1" ]]; do
  if ! kill -0 "$emulator_pid" 2>/dev/null; then
    echo "Android Emulator exited before completing boot" >&2
    exit 1
  fi
  if (( SECONDS >= boot_deadline )); then
    echo "Android Emulator did not finish booting within 300 seconds" >&2
    exit 1
  fi
  sleep 2
done

actual_api="$("$adb_bin" -s "$serial" shell getprop ro.build.version.sdk | tr -d '\r')"
is_emulator="$("$adb_bin" -s "$serial" shell getprop ro.kernel.qemu | tr -d '\r')"
if [[ "$actual_api" != "$api_level" || "$is_emulator" != "1" ]]; then
  echo "unexpected AVD identity: API=$actual_api ro.kernel.qemu=$is_emulator (expected API=$api_level and emulator=1)" >&2
  exit 1
fi
printf 'AVD ready: serial=%s api=%s reported_emulator=%s\n' "$serial" "$actual_api" "$is_emulator"

export ANDROID_SERIAL="$serial"
repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repository_root/android-supervisor"
./gradlew --no-daemon connectedDebugAndroidTest
