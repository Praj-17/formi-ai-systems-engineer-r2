#!/usr/bin/env bash
# Crash recovery test: kill controller mid-run, restart, verify completion
set -euo pipefail

echo "=== Crash Recovery Test ==="
echo

# Clean slate
rm -rf runs/crash_test runs/crash_ctrl
echo "1. Starting simulator..."
python3 -m sim serve --scenario scenarios/public_01_dev.yaml --run-dir runs/crash_test > /tmp/crash_sim.log 2>&1 &
SIM_PID=$!
sleep 5

if ! curl -s http://127.0.0.1:8700/health > /dev/null; then
    echo "ERROR: Simulator failed to start"
    kill $SIM_PID 2>/dev/null || true
    exit 1
fi

echo "   Simulator ready (PID: $SIM_PID)"
echo

echo "2. Starting controller..."
timeout 30 python3 -m controller.main --url http://127.0.0.1:8700 --run-dir runs/crash_ctrl > /tmp/crash_ctrl1.log 2>&1 &
CTRL_PID=$!

# Wait for it to process some ticks
sleep 15

echo "3. Killing controller at tick ~30..."
kill $CTRL_PID
wait $CTRL_PID 2>/dev/null || true

# Check state was saved
if [ ! -f runs/crash_ctrl/controller_state.json ]; then
    echo "ERROR: State file not found after crash"
    kill $SIM_PID 2>/dev/null || true
    exit 1
fi

LAST_CHUNK_BEFORE=$(python3 -c "import json; print(json.load(open('runs/crash_ctrl/controller_state.json'))['last_chunk'])")
LAST_TS_BEFORE=$(python3 -c "import json; print(json.load(open('runs/crash_ctrl/controller_state.json'))['current_ts'])")

echo "   Last chunk before crash: $LAST_CHUNK_BEFORE"
echo "   Last timestamp: $LAST_TS_BEFORE"
echo

echo "4. Restarting controller..."
timeout 180 python3 -m controller.main --url http://127.0.0.1:8700 --run-dir runs/crash_ctrl > /tmp/crash_ctrl2.log 2>&1 || true

# Check it completed
SIM_STATE=$(curl -s http://127.0.0.1:8700/sim/state)
FINISHED=$(echo "$SIM_STATE" | python3 -c "import json, sys; print(json.load(sys.stdin).get('finished', False))")

if [ "$FINISHED" == "True" ]; then
    echo "   ✓ Controller resumed and completed scenario"
else
    echo "   ✗ Controller did not finish (may have timed out)"
fi

LAST_CHUNK_AFTER=$(python3 -c "import json; print(json.load(open('runs/crash_ctrl/controller_state.json'))['last_chunk'])")
echo "   Last chunk after restart: $LAST_CHUNK_AFTER"

if [ "$LAST_CHUNK_AFTER" -gt "$LAST_CHUNK_BEFORE" ]; then
    echo "   ✓ Controller made progress after restart"
else
    echo "   ✗ Controller did not progress"
fi

# Cleanup
kill $SIM_PID 2>/dev/null || true
wait $SIM_PID 2>/dev/null || true

echo
echo "=== Crash Recovery Test Complete ==="
echo "Logs:"
echo "  - runs/crash_ctrl/audit_log.jsonl"
echo "  - /tmp/crash_ctrl1.log (before crash)"
echo "  - /tmp/crash_ctrl2.log (after restart)"
