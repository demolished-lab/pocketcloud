#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python was not found. Install it in Termux with: pkg install python" >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("PocketCloud Stage 1 requires Python 3.11 or later")
PY

export PYTHONPATH="$ROOT/runtime${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"
exec "$PYTHON_BIN" -m pocketcloud serve
