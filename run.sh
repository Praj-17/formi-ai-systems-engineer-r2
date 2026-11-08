#!/usr/bin/env bash
# Outcome-first agent loop controller
set -euo pipefail
SIM_URL="${1:?usage: ./run.sh <SIM_URL>}"
RUN_DIR="${2:-runs/controller}"

echo "Starting controller against $SIM_URL" >&2
exec python3 -m controller.main --url "$SIM_URL" --run-dir "$RUN_DIR"
