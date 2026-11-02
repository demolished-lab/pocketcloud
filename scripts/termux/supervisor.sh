#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
DATA_DIR_INPUT="${POCKETCLOUD_DATA_DIR:-$HOME/.local/share/pocketcloud}"
PORT="${POCKETCLOUD_PORT:-8765}"

fail() { printf 'PocketCloud supervisor: %s\n' "$1" >&2; exit 1; }

command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Python was not found; install it with: pkg install python"
if ! DATA_DIR="$("$PYTHON_BIN" - "$HOME" "$DATA_DIR_INPUT" <<'PY'
import sys
from pathlib import Path

home_arg = Path(sys.argv[1])
requested = Path(sys.argv[2])
if ".." in requested.parts:
    raise SystemExit(2)
home = home_arg.resolve(strict=True)
if not requested.is_absolute():
    requested = home_arg / requested
try:
    relative = requested.relative_to(home_arg)
except ValueError:
    try:
        relative = requested.relative_to(home)
    except ValueError:
        raise SystemExit(2)
if not relative.parts:
    raise SystemExit(2)
candidate = home.joinpath(relative)
cursor = home
for part in relative.parts:
    cursor = cursor / part
    if cursor.is_symlink():
        raise SystemExit(2)
resolved = candidate.resolve(strict=False)
if resolved != candidate or not resolved.is_relative_to(home):
    raise SystemExit(2)
print(candidate)
PY
)"; then
  fail "state directory must be under Termux home with no traversal or symlinked components"
fi
PID_FILE="$DATA_DIR/runtime.pid"
LOG_FILE="$DATA_DIR/runtime.log"
PID_TMP="$DATA_DIR/runtime.pid.tmp"
[[ "$PORT" =~ ^[0-9]+$ ]] && (( PORT >= 1024 && PORT <= 65535 )) || fail "invalid PocketCloud port"

mkdir -p "$DATA_DIR"
[[ ! -L "$DATA_DIR" ]] || fail "refusing a symlinked state directory"
chmod 700 "$DATA_DIR"
[[ ! -L "$PID_FILE" && ! -L "$PID_TMP" && ! -L "$LOG_FILE" ]] || fail "refusing symlinked runtime state files"

runtime_matches_pid() {
  local pid="$1" cmdline cwd
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  [[ -r "/proc/$pid/cmdline" && -r "/proc/$pid/cwd" ]] || return 1
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null || true)"
  [[ "$cwd" == "$ROOT" && "$cmdline" == *"pocketcloud"* && "$cmdline" == *"serve"* ]]
}

read_runtime_pid() {
  [[ -f "$PID_FILE" && ! -L "$PID_FILE" ]] || return 1
  local pid
  IFS= read -r pid < "$PID_FILE" || return 1
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  printf '%s' "$pid"
}

health_check() {
  "$PYTHON_BIN" - "$PORT" <<'PY'
import json
import sys
import urllib.request

url = f"http://127.0.0.1:{int(sys.argv[1])}/readyz"
try:
    with urllib.request.urlopen(url, timeout=1.5) as response:
        value = json.loads(response.read(4096).decode("utf-8"))
        if response.status != 200 or value.get("status") != "ok":
            raise SystemExit(1)
except Exception:
    raise SystemExit(1)
PY
}

start_runtime() {
  if pid="$(read_runtime_pid 2>/dev/null)" && runtime_matches_pid "$pid"; then
    printf 'PocketCloud runtime already running (pid %s).\n' "$pid"
    health_check && exit 0
    fail "process exists but readiness check failed; inspect $LOG_FILE"
  fi
  [[ ! -L "$PID_FILE" && ! -L "$PID_TMP" && ! -L "$LOG_FILE" ]] || fail "refusing symlinked runtime state files"
  rm -f "$PID_FILE"

  (
    cd "$ROOT"
    export POCKETCLOUD_DATA_DIR="$DATA_DIR"
    export POCKETCLOUD_PORT="$PORT"
    export PYTHONPATH="$ROOT/runtime${PYTHONPATH:+:$PYTHONPATH}"
    nohup "$PYTHON_BIN" -m pocketcloud serve --host 127.0.0.1 --port "$PORT" >>"$LOG_FILE" 2>&1 </dev/null &
    child=$!
    printf '%s\n' "$child" > "$PID_TMP"
    chmod 600 "$PID_TMP"
    mv -f "$PID_TMP" "$PID_FILE"
  )

  for _ in $(seq 1 200); do
    if pid="$(read_runtime_pid 2>/dev/null)" && runtime_matches_pid "$pid" && health_check; then
      printf 'PocketCloud runtime ready on 127.0.0.1:%s (pid %s).\n' "$PORT" "$pid"
      exit 0
    fi
    if [[ -f "$PID_FILE" ]] && ! pid="$(read_runtime_pid 2>/dev/null)"; then
      fail "runtime did not start; inspect $LOG_FILE"
    fi
    sleep 0.1
  done
  fail "runtime did not become ready within 20 seconds; inspect $LOG_FILE"
}

stop_runtime() {
  if ! pid="$(read_runtime_pid 2>/dev/null)"; then
    [[ ! -L "$PID_FILE" ]] || fail "refusing a symlinked PID file"
    rm -f "$PID_FILE"
    printf 'PocketCloud runtime is not running.\n'
    exit 0
  fi
  if ! runtime_matches_pid "$pid"; then
    if kill -0 "$pid" 2>/dev/null; then
      fail "PID $pid is alive but not confirmed as PocketCloud; refusing to signal or remove its record"
    fi
    rm -f "$PID_FILE"
    printf 'Removed a stale PocketCloud PID record; no process was signalled.\n'
    exit 0
  fi

  kill -TERM "$pid" || fail "could not request graceful shutdown"
  for _ in $(seq 1 100); do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$PID_FILE"
      printf 'PocketCloud runtime stopped.\n'
      exit 0
    fi
    sleep 0.1
  done
  fail "runtime did not stop after SIGTERM; it was not force-killed"
}

status_runtime() {
  if pid="$(read_runtime_pid 2>/dev/null)" && runtime_matches_pid "$pid"; then
    if health_check; then
      printf 'PocketCloud runtime ready on 127.0.0.1:%s (pid %s).\n' "$PORT" "$pid"
      exit 0
    fi
    printf 'PocketCloud process exists (pid %s), but readiness failed.\n' "$pid" >&2
    exit 2
  fi
  printf 'PocketCloud runtime is not running.\n'
  exit 3
}

case "${1:-}" in
  start) start_runtime ;;
  stop) stop_runtime ;;
  status) status_runtime ;;
  *) fail "allowed verbs: start, stop, status" ;;
esac
