#!/usr/bin/env bash
set -euo pipefail
DEV=${1:-}
LOG=${2:-/tmp/touch_log.csv}
if [[ -z "${DEV}" ]]; then
  echo "Usage: $0 /dev/input/eventX [log.csv]" >&2
  exit 2
fi
python3 test_touch.py --device "$DEV" --log "$LOG"
